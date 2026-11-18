"""One request over stdin, one response over stdout. Used by desktop and web."""
import contextlib
import json
import sys

from engine import handle

MAX_BYTES = 2_000_000


def main():
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        raw = sys.stdin.buffer.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("Arquivo maior que 2 MB.")
        request = json.loads(raw)
        with contextlib.redirect_stdout(sys.stderr):
            data = handle(request)
        response = dict(ok=True, data=data)
    except (ValueError, TypeError, KeyError, IndexError, ZeroDivisionError) as exc:
        response = dict(ok=False, error=str(exc))
    except Exception:
        import traceback
        traceback.print_exc(file=sys.stderr)
        response = dict(ok=False, error="Falha numérica inesperada. Revise os dados e consulte o log do motor.")
    sys.stdout.write(json.dumps(response, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
