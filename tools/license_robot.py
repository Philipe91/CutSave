"""Robo de ativacao — emite licencas AUTOMATICAMENTE a partir de e-mails.

Roda no PC do dono (a chave privada NUNCA sai daqui). A cada ciclo, le a caixa
de entrada da conta de ativacao (IMAP), procura pedidos com:

    ID da Maquina:    PN-XXXX-XXXX-XXXX-XXXX  (o app do cliente preenche)
    Codigo de compra: PNC-XXXX-XXXX           (entregue na venda)

Valida o codigo (tools/vouchers.py), assina a licenca (tools/issuer.py) e
RESPONDE o e-mail com a chave. Uso unico por codigo; o mesmo PC pedindo de novo
recebe a MESMA chave (perdeu o e-mail); outro PC com codigo usado e recusado.

Configuracao: copie tools/robot_config.example.json para tools/robot_config.json
(gitignored) e preencha com a conta dedicada (Gmail: ative 2FA e crie uma
"senha de app"). Inicie com tools/iniciar_robo_licencas.bat.
"""

from __future__ import annotations

import email
import email.utils
import imaplib
import json
import re
import smtplib
import sys
import time
from datetime import datetime
from email.header import decode_header
from email.message import EmailMessage
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.issuer import issue_license, load_private_key  # noqa: E402
from tools.vouchers import VoucherStore, normalize  # noqa: E402

CONFIG_PATH = Path(__file__).with_name("robot_config.json")
LOG_PATH = Path(__file__).with_name("licenses_emitidas") / "robo-log.jsonl"
PROCESSED_PATH = Path(__file__).with_name("licenses_emitidas") / "processados.json"

MACHINE_RE = re.compile(r"PN(?:-[A-Z0-9]{4}){4}")
VOUCHER_RE = re.compile(r"PNC[\s-]*([A-Z0-9]{4})[\s-]*([A-Z0-9]{4})")
# remetentes de sistema: nunca responder (evita loop com bounces/robos)
_NO_REPLY = ("mailer-daemon", "postmaster", "no-reply", "noreply", "nao-responda")


# ---- nucleo (puro, testavel) ----
def extract_request(text: str) -> tuple[str, str]:
    """Acha (machine_id, voucher) no texto do e-mail; '' quando ausente."""
    up = text.upper()
    mid = MACHINE_RE.search(up)
    vou = VOUCHER_RE.search(up)
    voucher = normalize(f"PNC{vou.group(1)}{vou.group(2)}") if vou else ""
    return (mid.group(0) if mid else "", voucher)


def process_request(
    store: VoucherStore, machine_id: str, voucher: str, customer: str, issue
) -> tuple[bool, str]:
    """Decide a resposta. 'issue' = callable(machine_id, customer) -> chave.

    Retorna (emitiu_ou_reenviou, corpo_da_resposta).
    """
    if not machine_id:
        return False, (
            "Olá! Não encontramos o ID da Máquina no seu e-mail.\n\n"
            "Abra o PrintNest, copie o ID (formato PN-XXXX-XXXX-XXXX-XXXX) na "
            "tela de Ativação e envie novamente junto com o seu código de compra."
        )
    if not voucher:
        return False, (
            "Olá! Não encontramos o seu código de compra (formato PNC-XXXX-XXXX).\n\n"
            "Ele foi entregue na confirmação da sua compra. Envie novamente o "
            "e-mail com o ID da Máquina e o código de compra juntos."
        )
    rec = store.find(voucher)
    if rec is None:
        return False, (
            f"Olá! O código de compra {voucher} não foi reconhecido.\n\n"
            "Confira se digitou exatamente como recebeu. Se o problema "
            "continuar, responda este e-mail que o suporte verifica."
        )
    if rec["used"]:
        if rec["machine_id"] == machine_id and rec["key"]:
            return True, _reply_with_key(rec["key"], reissued=True)
        return False, (
            f"Olá! O código {voucher} já foi utilizado em outro computador.\n\n"
            "Cada código ativa 1 PC. Para transferir a licença de um PC para "
            "outro, use Ajuda → Licença → Desativar no PC antigo e responda "
            "este e-mail informando a troca."
        )
    key = issue(machine_id, customer)
    store.redeem(voucher, machine_id, customer, key)
    return True, _reply_with_key(key, reissued=False)


def _reply_with_key(key: str, *, reissued: bool) -> str:
    intro = (
        "Olá! Reenviando a sua chave de licença (este PC já estava ativado):"
        if reissued
        else "Olá! Obrigado pela compra. Aqui está a sua chave de licença do PrintNest Pro:"
    )
    return (
        f"{intro}\n\n"
        f"{key}\n\n"
        "Como ativar:\n"
        "1. Abra o PrintNest;\n"
        "2. Na tela de Ativação, cole a chave inteira no campo do passo 2;\n"
        "3. Clique em Ativar. Pronto — o programa fica liberado neste PC.\n\n"
        "Guarde este e-mail. Qualquer dúvida, é só responder."
    )


class ProcessedLog:
    """Message-IDs ja tratados (persistido). O robo NAO confia na flag 'lida'
    do e-mail: ler a caixa no navegador marcaria como lida e o pedido sumiria.
    So entra aqui DEPOIS de tratado com sucesso — erro no meio = tenta de novo
    no proximo ciclo."""

    def __init__(self, path: Path | str | None = None) -> None:
        self._path = Path(path) if path else PROCESSED_PATH
        self._ids: set[str] = set()
        if self._path.exists():
            self._ids = set(json.loads(self._path.read_text(encoding="utf-8")))

    def has(self, msg_id: str) -> bool:
        return msg_id in self._ids

    def add(self, msg_id: str) -> None:
        self._ids.add(msg_id)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(sorted(self._ids)), encoding="utf-8")
        tmp.replace(self._path)


# ---- plumbing de e-mail ----
def load_config(path: Path = CONFIG_PATH) -> dict:
    if not path.exists():
        raise FileNotFoundError(
            f"Configuracao ausente: {path}. Copie robot_config.example.json "
            "para robot_config.json e preencha a conta de e-mail."
        )
    cfg = json.loads(path.read_text(encoding="utf-8"))
    for k in ("email", "app_password"):
        if not cfg.get(k):
            raise ValueError(f"Campo '{k}' vazio em {path}.")
    cfg.setdefault("imap_host", "imap.gmail.com")
    cfg.setdefault("smtp_host", "smtp.gmail.com")
    cfg.setdefault("poll_seconds", 60)
    return cfg


def _decode(value: str | None) -> str:
    if not value:
        return ""
    parts = []
    for chunk, enc in decode_header(value):
        parts.append(
            chunk.decode(enc or "utf-8", "replace") if isinstance(chunk, bytes) else chunk
        )
    return "".join(parts)


def _body_text(msg: email.message.Message) -> str:
    """Texto plano do e-mail (fallback: HTML sem tags)."""
    plain, html = "", ""
    parts = msg.walk() if msg.is_multipart() else [msg]
    for part in parts:
        ctype = part.get_content_type()
        if ctype not in ("text/plain", "text/html"):
            continue
        payload = part.get_payload(decode=True)
        if payload is None:
            continue
        text = payload.decode(part.get_content_charset() or "utf-8", "replace")
        if ctype == "text/plain" and not plain:
            plain = text
        elif ctype == "text/html" and not html:
            html = text
    return plain or re.sub(r"<[^>]+>", " ", html)


def _send_reply(cfg: dict, to_addr: str, subject: str, body: str) -> None:
    reply = EmailMessage()
    reply["From"] = cfg["email"]
    reply["To"] = to_addr
    reply["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    reply.set_content(body + "\n\n— PrintNest Pro (ativação automática)")
    with smtplib.SMTP_SSL(cfg["smtp_host"], 465, timeout=30) as smtp:
        smtp.login(cfg["email"], cfg["app_password"])
        smtp.send_message(reply)


def _log(entry: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry["at"] = datetime.now().isoformat(timespec="seconds")
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"[{entry['at']}] {entry.get('result', '')}: {entry.get('from', '')}", flush=True)


def check_inbox(cfg: dict, store: VoucherStore, issue, processed: ProcessedLog) -> int:
    """Um ciclo: trata as mensagens ainda nao processadas. Retorna quantas.

    Nao usa a flag 'lida' (BODY.PEEK nao marca nada): o controle e o registro
    proprio (ProcessedLog), gravado SO depois do tratamento dar certo.
    """
    handled = 0
    with imaplib.IMAP4_SSL(cfg["imap_host"], 993, timeout=30) as imap:
        imap.login(cfg["email"], cfg["app_password"])
        imap.select("INBOX")
        _, data = imap.search(None, "ALL")
        for num in data[0].split():
            _, fetched = imap.fetch(num, "(BODY.PEEK[])")
            msg = email.message_from_bytes(fetched[0][1])
            msg_id = (msg.get("Message-ID") or "").strip() or f"sem-id-{num.decode()}"
            if processed.has(msg_id):
                continue
            sender_name, sender_addr = email.utils.parseaddr(_decode(msg.get("From")))
            subject = _decode(msg.get("Subject"))
            low = sender_addr.lower()
            if not sender_addr or low == cfg["email"].lower() or any(
                bad in low for bad in _NO_REPLY
            ):
                processed.add(msg_id)  # sistema/robo: nunca responder
                continue
            text = f"{subject}\n{_body_text(msg)}"
            machine_id, voucher = extract_request(text)
            if not machine_id and not voucher:
                processed.add(msg_id)
                _log({"from": sender_addr, "result": "ignorado (sem ID/codigo)"})
                continue
            customer = f"{sender_name} <{sender_addr}>" if sender_name else sender_addr
            ok, body = process_request(store, machine_id, voucher, customer, issue)
            _send_reply(cfg, sender_addr, subject or "Ativação PrintNest", body)
            processed.add(msg_id)  # so apos responder: erro acima = repete depois
            _log({
                "from": sender_addr, "machine_id": machine_id, "voucher": voucher,
                "result": "chave enviada" if ok else "recusado/orientado",
            })
            handled += 1
    return handled


def main() -> None:
    cfg = load_config()
    private = load_private_key()  # falha cedo se o segredo nao estiver aqui

    def issue(machine_id: str, customer: str) -> str:
        return issue_license(machine_id, customer, private_key=private)

    store = VoucherStore()
    processed = ProcessedLog()
    print("Robo de ativacao do PrintNest — Ctrl+C para parar.", flush=True)
    print(f"Conta: {cfg['email']} · ciclo a cada {cfg['poll_seconds']}s", flush=True)
    while True:
        try:
            n = check_inbox(cfg, store, issue, processed)
            if n:
                print(f"  -> {n} pedido(s) tratado(s) neste ciclo", flush=True)
        except KeyboardInterrupt:
            raise
        except Exception as exc:  # rede/IMAP fora do ar: tenta no proximo ciclo
            print(
                f"  !! erro no ciclo ({type(exc).__name__}: {exc}) — vou tentar de novo",
                flush=True,
            )
        time.sleep(int(cfg["poll_seconds"]))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nRobo encerrado.")
