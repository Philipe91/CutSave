"""Licenciamento do PrintNest (offline, chave assinada Ed25519).

O app carrega SO a chave publica: verifica a assinatura da licenca, mas nao
consegue forjar uma. A chave privada fica com o dono do produto (emite as
licencas com tools/gen_license.py). Modelo: node-locked (presa ao PC) com
trial; sem licenca valida o app funciona, mas a exportacao fica travada.
"""
