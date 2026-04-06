# Revisão técnica do bot completo (versão monolítica ~1837 linhas)

## Resumo direto

O bot está funcional, mas hoje tem três gargalos principais:

1. **Acoplamento alto** (visão + decisão + input + menu no mesmo arquivo).
2. **Confiabilidade limitada** (muitos `except: pass`, pouco diagnóstico).
3. **Performance instável** (múltiplos screenshots/OCR por loop).

## Problemas mais importantes (ordem de impacto)

### 1) Silenciamento de erro excessivo
- Há vários pontos com `except Exception: pass`.
- Isso mascara falhas reais de OCR, teclado, templates e foco.

**Melhoria**
- Trocar por `logging.exception(...)` ou, no mínimo, `logging.debug(...)`.
- Manter `pass` só em casos realmente esperados e documentados.

---

### 2) Estado global compartilhado e concorrência
- Uso de globais (`_config`, `_panel_cache`, `_stop_hp`, `_stop_requested`) em múltiplas rotinas/threads.
- Risco de corrida e comportamento imprevisível em execução longa.

**Melhoria**
- Introduzir objeto `AppState` com locks explícitos para cache/config.
- Encapsular leitura/escrita de config e cache em funções thread-safe.

---

### 3) Uso de `time.time()` em timeout/cooldown
- `time.time()` depende do relógio do sistema; ajustes de hora podem quebrar lógica.

**Melhoria**
- Usar `time.monotonic()` para cooldown, timeout de waypoint e sleeps interruptíveis.

---

### 4) Loop caro por frame (screenshot + OCR repetidos)
- Em vários fluxos o frame é recapturado em sequência para HP/Mana/Coords.
- OCR em alta frequência aumenta custo e jitter.

**Melhoria**
- Um **frame por tick** e reutilização desse frame nas leituras do mesmo ciclo.
- OCR com taxa menor (ex.: a cada N ticks) quando possível.

---

### 5) Persistência de config com gravações frequentes
- `save_config()` é chamado em caminhos críticos (aprendizagem de mana, calibração parcial).

**Melhoria**
- Debounce de escrita (ex.: agrupar e salvar a cada X segundos ou em evento).
- Escrita atômica (`tmp` + rename) para evitar arquivo corrompido.

---

### 6) Falta de telemetria operacional
- Hoje há prints, mas faltam métricas de sessão para depuração e tuning.

**Melhoria**
- Log estruturado (JSON ou formato fixo) com:
  - tempo de loop;
  - taxa de OCR válido;
  - revives disparados;
  - pulos de waypoint/timeouts.

---

### 7) Validação de configuração insuficiente
- Muitos campos dependem de formato específico (`offsets`, thresholds, teclas, ranges).

**Melhoria**
- Validar schema ao carregar config.
- Fallback seguro com aviso quando campo estiver inválido.

---

### 8) UX e manutenção
- Menu mostra versões mistas em alguns pontos (V11/V12/V13), gerando confusão.

**Melhoria**
- Definir versão única e exibir build/info no menu.

## Melhorias táticas (rápidas e de alto retorno)

1. **Trocar todos os timeouts/cooldowns para `monotonic`**.
2. **Adicionar logging real** em todos os `except` críticos.
3. **Frame único por tick** (pipeline de leitura compartilhada).
4. **Circuit breaker por módulo** (visão/movimento/input separados).
5. **Modo dry-run** para validar decisão sem apertar tecla.

## Erros potenciais que merecem teste dedicado

- Teclas presas se ocorrer exceção entre `keyDown` e `soltar_todas_teclas`.
- Leitura de mana máxima aprendendo valor errado por OCR espúrio.
- Template matching com cache antigo após mover/janela redimensionada.
- Regressão de coord quando regex falha em OCR parcial.

## Plano recomendado (incremental)

### Fase 1 (curto prazo)
- Instrumentação/logs + monotonic + limpeza de `except: pass`.
- Resultado: maior previsibilidade e depuração real.

### Fase 2
- Refatorar em módulos: `vision.py`, `navigation.py`, `revive.py`, `state.py`, `ui.py`.
- Resultado: menor acoplamento e evolução mais segura.

### Fase 3
- Testes com fixtures de imagem para OCR/template matching.
- Resultado: menos regressão ao ajustar thresholds e filtros.

## Conclusão

O bot já funciona, mas está no limite da manutenibilidade por ser monolítico e pouco observável.
A melhor estratégia é **não reescrever tudo de uma vez**; aplicar melhorias estruturais em etapas curtas,
priorizando estabilidade (monotonic + logs + frame único por tick) antes de novas features.
