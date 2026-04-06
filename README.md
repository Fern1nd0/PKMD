# PKMD

Estrutura mínima do projeto:

- `README.md`
- `pkmd_bot_v13.py`
- `config/pkmd_bot_config.json` (gerado automaticamente na 1ª execução)
- `logs/pkmd_bot.log` (gerado automaticamente)

## Execução local

```bash
python3 pkmd_bot_v13.py --max-runtime 10
```

## Opções úteis

- `--verbose` ativa logs DEBUG
- `--config caminho/arquivo.json` usa outro arquivo de config
- `--max-runtime N` encerra automaticamente após N segundos
- `--dry-run` força modo simulação
- `--live` força modo real (desativa dry-run)
- `--report-every N` define frequência de log de progresso

## Objetivo

Manter a evolução do bot concentrada no arquivo principal `pkmd_bot_v13.py`,
com uma base estável para incrementos reais.

## Revisão técnica

- Ver relatório: `REVISAO_BOT_COMPLETO.md`.
