"""PKMD bot v13.

Entrypoint único com base real para evolução:
- configuração em JSON;
- loop com time.monotonic();
- parada segura por sinais;
- métricas e circuit breaker;
- suporte a modo dry-run.
"""

from __future__ import annotations

import argparse
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import signal
import threading
import time
from dataclasses import asdict
from dataclasses import dataclass
from enum import Enum
from typing import Any
from typing import Optional


class BotState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    STOPPED = "stopped"


@dataclass
class BotConfig:
    tick_seconds: float = 0.2
    max_errors: int = 5
    dry_run: bool = True
    report_every_ticks: int = 50
    max_runtime_seconds: float = 0.0

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "BotConfig":
        cfg = cls(
            tick_seconds=float(payload.get("tick_seconds", cls.tick_seconds)),
            max_errors=int(payload.get("max_errors", cls.max_errors)),
            dry_run=bool(payload.get("dry_run", cls.dry_run)),
            report_every_ticks=int(payload.get("report_every_ticks", cls.report_every_ticks)),
            max_runtime_seconds=float(payload.get("max_runtime_seconds", cls.max_runtime_seconds)),
        )

        if cfg.tick_seconds <= 0:
            raise ValueError("tick_seconds deve ser > 0")
        if cfg.max_errors < 1:
            raise ValueError("max_errors deve ser >= 1")
        if cfg.report_every_ticks < 1:
            raise ValueError("report_every_ticks deve ser >= 1")
        if cfg.max_runtime_seconds < 0:
            raise ValueError("max_runtime_seconds deve ser >= 0")
        return cfg


@dataclass
class RuntimeMetrics:
    ticks: int = 0
    errors: int = 0
    started_at: float = 0.0


class PKMDBot:
    def __init__(self, config: Optional[BotConfig] = None) -> None:
        self.config = config or BotConfig()
        self.state = BotState.IDLE
        self._error_count = 0
        self._stop_event = threading.Event()
        self.metrics = RuntimeMetrics()

    def start(self) -> None:
        if self.state == BotState.RUNNING:
            return

        self.state = BotState.RUNNING
        self.metrics.started_at = time.monotonic()
        logging.info("Bot iniciado | dry_run=%s", self.config.dry_run)
        self._run_loop()

    def stop(self) -> None:
        self._stop_event.set()
        self.state = BotState.STOPPED
        uptime = time.monotonic() - self.metrics.started_at if self.metrics.started_at else 0.0
        logging.info(
            "Bot finalizado | ticks=%s erros=%s uptime=%.2fs",
            self.metrics.ticks,
            self.metrics.errors,
            uptime,
        )

    def _sleep_interruptible(self, seconds: float) -> bool:
        end_at = time.monotonic() + max(0.0, seconds)
        while time.monotonic() < end_at:
            if self._stop_event.is_set():
                return False
            remaining = end_at - time.monotonic()
            time.sleep(min(0.05, max(0.0, remaining)))
        return True

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            if self._should_stop_for_runtime_limit():
                logging.warning("Limite de runtime atingido. Encerrando.")
                self.stop()
                break

            try:
                self._tick()
                self._error_count = 0
                self.metrics.ticks += 1
                if self.metrics.ticks % self.config.report_every_ticks == 0:
                    logging.info("Progresso | ticks=%s erros=%s", self.metrics.ticks, self.metrics.errors)
                if not self._sleep_interruptible(self.config.tick_seconds):
                    break
            except Exception as exc:  # noqa: BLE001
                self._error_count += 1
                self.metrics.errors += 1
                logging.exception("Falha no loop: %s", exc)
                if self._error_count >= self.config.max_errors:
                    logging.error("Circuit breaker acionado por excesso de falhas")
                    self.stop()

    def _should_stop_for_runtime_limit(self) -> bool:
        if self.config.max_runtime_seconds <= 0:
            return False
        return (time.monotonic() - self.metrics.started_at) >= self.config.max_runtime_seconds

    def _tick(self) -> None:
        """Um ciclo de trabalho.

        TODO:
        - Ler estado do jogo
        - Tomar decisão por regras
        - Executar ação permitida
        """
        if self.config.dry_run:
            logging.debug("tick executado (dry-run)")
            return
        logging.debug("tick executado")


def _configure_logging(log_dir: Path, verbose: bool = False) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "pkmd_bot.log"

    level = logging.DEBUG if verbose else logging.INFO
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(level)

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(stream_handler)
    root.addHandler(file_handler)


def _load_or_create_config(config_path: Path) -> BotConfig:
    if not config_path.exists():
        config_path.parent.mkdir(parents=True, exist_ok=True)
        cfg = BotConfig()
        config_path.write_text(json.dumps(asdict(cfg), indent=2, ensure_ascii=False), encoding="utf-8")
        return cfg

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    return BotConfig.from_dict(payload)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PKMD bot v13")
    parser.add_argument("--config", default="config/pkmd_bot_config.json", help="Caminho do arquivo de config")
    parser.add_argument("--verbose", action="store_true", help="Ativa logs DEBUG")
    parser.add_argument(
        "--max-runtime",
        type=float,
        default=None,
        help="Sobrescreve max_runtime_seconds da configuração",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    config_path = Path(args.config)
    cfg = _load_or_create_config(config_path)
    if args.max_runtime is not None:
        cfg.max_runtime_seconds = args.max_runtime

    _configure_logging(log_dir=Path("logs"), verbose=args.verbose)
    bot = PKMDBot(cfg)

    def _handle_stop(_signum: int, _frame: object) -> None:
        logging.info("Sinal de parada recebido")
        bot.stop()

    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGTERM, _handle_stop)

    bot.start()


if __name__ == "__main__":
    main()
