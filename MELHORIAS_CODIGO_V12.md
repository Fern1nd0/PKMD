# Melhorias recomendadas para o código V12/V13

Este checklist é focado no código grande de automação (OCR + OpenCV + hotkeys + cavebot).

## 1) Prioridade alta (estabilidade)

- **Trocar `time.time()` por `time.monotonic()`** em cooldowns e timeouts (`sleep_interruptible`, `hp_cooldown`, `timeout_waypoint`).
- **Centralizar captura de tela** em um único produtor (thread) para evitar múltiplos `pyautogui.screenshot()` concorrentes.
- **Evitar `except Exception: pass` silencioso**: registrar ao menos `logging.debug/exception` para diagnósticos.
- **Adicionar validação forte de config** (tipos/intervalos) ao carregar JSON.

## 2) Organização de código

- Dividir em módulos:
  - `config.py`
  - `vision.py` (OCR/template matching)
  - `movement.py`
  - `revive.py`
  - `ui_menu.py`
- Manter `pkmd_bot_v13.py` apenas como entrypoint.

## 3) Performance

- Reusar frame por tick para HP/Mana/coords no mesmo ciclo.
- Cachear templates pré-processados em memória (gray + tamanhos).
- Diminuir OCR agressivo: OCR só quando template/painel estiver estável.

## 4) Confiabilidade do OCR

- Guardar uma janela deslizante (N leituras) e usar mediana/moda.
- Descartar leituras impossíveis (ex.: mana > limite lógico do personagem).
- Persistir estatísticas de confiança por leitura para calibrar thresholds.

## 5) Segurança operacional

- Implementar **modo dry-run** (sem enviar teclas) para validar decisões.
- Adicionar kill switch redundante além do `END` (ex.: `ctrl+shift+q`).
- Em qualquer erro crítico: `soltar_todas_teclas()` + estado STOPPED.

## 6) Testabilidade

- Criar testes unitários para:
  - `parse_coords_text`
  - `normalize_text`
  - `_calculate_mana_percent`
  - `_percent_from_bar_mask`
- Criar pasta de fixtures com imagens estáticas para testes de visão.

## 7) UX de operação

- Mostrar versão consistente no menu (evitar V11/V12/V13 misturado).
- Salvar logs em arquivo rotativo (`logs/pkmd.log`).
- Exibir status consolidado por linha com timestamp.

## 8) Plano rápido (3 passos)

1. **Refactor mínimo**: `monotonic`, logging e validação de config.
2. **Separação em módulos** + testes unitários de parser/matemática.
3. **Pipeline de visão** com frame único por tick e métricas de confiança.
