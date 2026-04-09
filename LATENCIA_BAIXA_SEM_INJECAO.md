# Latência baixa sem injeção no jogo

> Não uso nem recomendo injeção de memória/DLL no cliente do jogo.
> Além de risco de banimento, isso cruza limites de segurança e manutenção.

## Meta prática

Para reação de revive quase instantânea, trabalhe com **budget de 20–30ms por ciclo** e caminho crítico curto:

1. Captura de frame da ROI do HP
2. Cálculo do percentual (sem OCR)
3. Decisão de revive
4. Disparo da tecla

## O que mais reduz delay de verdade

- **Remover OCR do caminho de HP** (usar barra por cor/ocupação de pixels).
- **Usar ROI fixa pós-calibração** (evitar template matching em todo tick).
- **Thread dedicada de captura** (producer/consumer com frame mais recente).
- **Um frame por tick** para todas as leituras do ciclo.
- **Gatilho de emergência**: se HP <= limiar, revive imediato sem confirmações extras.
- **Separar logging/print da thread crítica** para não atrasar reação.

## Configuração sugerida para teste

- `tick_seconds`: 0.02 a 0.04
- `loop_budget_ms`: 25
- `hp_confirmacoes`: 1 (apenas no modo emergência)
- `hp_cooldown`: o menor valor seguro para seu jogo

## Medição obrigatória

Sem medir, otimização vira chute. Registre:

- tempo de ciclo (ms)
- percentual de ciclos acima do budget
- maior tick observado
- tempo entre HP<=limiar e envio da tecla

## Próximos passos no código

1. Implementar pipeline de frame único por tick.
2. Criar `ReviveController` com modo emergência.
3. Adicionar métrica de latência fim-a-fim do revive.
4. Só depois mexer em OCR/mana/coord para não contaminar o caminho crítico.
