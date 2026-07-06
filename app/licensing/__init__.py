"""Licenciamento do PrintNest (offline, chave assinada Ed25519).

O app carrega SO a chave publica: verifica a assinatura da licenca, mas nao
consegue forjar uma. A chave privada fica com o dono do produto (emissao via
tools/license_studio.py, gen_license.py ou o robo license_robot.py). Modelo:
compra completa + chave node-locked (presa ao PC), SEM trial — sem licenca
valida o executavel nao abre (rodando do fonte, dev, nao trava).
"""

# Conta monitorada pelo robo de ativacao (tools/license_robot.py). O dialogo de
# ativacao monta um e-mail pronto para este endereco; o robo responde com a
# chave. Trocar aqui se a conta mudar (e refazer o build).
ACTIVATION_EMAIL = "ativacao.printnest@gmail.com"
