"""Compatibility entry point. Keep this file inside the extracted project."""
from start_ekt import main


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print('\nЗапуск отменён.')
        raise SystemExit(130)
