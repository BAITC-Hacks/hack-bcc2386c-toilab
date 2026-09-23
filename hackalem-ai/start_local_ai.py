"""One-window local launch. Only processes created by this script are stopped."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent
STATE = ROOT / '.local-ai'
MODEL = 'qwen3:4b'
OLLAMA = 'http://127.0.0.1:11434'
INSTALL_URL = 'https://ollama.com/download/windows'
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def request(path, data=None, timeout=5):
    body = json.dumps(data, ensure_ascii=False).encode('utf-8') if data is not None else None
    headers = {'Content-Type': 'application/json'} if body is not None else {}
    return HTTP.open(urllib.request.Request(OLLAMA + path, data=body, headers=headers), timeout=timeout)


def read_json(url, timeout=3):
    with HTTP.open(url, timeout=timeout) as response:
        return json.load(response)


def busy_ports(ports):
    occupied = []
    for port in ports:
        with socket.socket() as sock:
            sock.settimeout(.2)
            if sock.connect_ex(('127.0.0.1', port)) == 0:
                occupied.append(port)
    return occupied


def installed_ollama():
    executable = shutil.which('ollama')
    if executable:
        return executable
    local = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'Programs/Ollama/ollama.exe'
    return str(local) if local.is_file() else None


def ollama_ready():
    try:
        with request('/api/tags') as response:
            data = json.load(response)
            return isinstance(data.get('models'), list)
    except (OSError, ValueError):
        return False


def ensure_python():
    if sys.version_info < (3, 11):
        raise RuntimeError('Нужен Python 3.11 или новее. Установите его и повторите запуск.')
    env_path = ROOT / '.venv'
    executable = env_path / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not executable.exists():
        print('Создаю отдельное окружение проекта…', flush=True)
        subprocess.run([sys.executable, '-m', 'venv', str(env_path)], check=True)
    digest = hashlib.sha256((ROOT / 'requirements.txt').read_bytes()).hexdigest()
    marker = STATE / 'requirements.sha256'
    if not marker.exists() or marker.read_text(encoding='utf-8') != digest:
        print('Устанавливаю библиотеки. Дождитесь окончания…', flush=True)
        subprocess.run([str(executable), '-m', 'pip', 'install', '-r', str(ROOT / 'requirements.txt')], check=True)
        marker.write_text(digest, encoding='utf-8')
    return str(executable)


def ensure_ollama(children, logs):
    if ollama_ready():
        return
    executable = installed_ollama()
    if not executable:
        print('\nНужно один раз установить Ollama. Сейчас откроется официальный сайт.')
        print('Нажмите Download for Windows, запустите скачанный установщик и установите программу.')
        webbrowser.open(INSTALL_URL)
        input('После завершения установки вернитесь сюда и нажмите Enter… ')
        if ollama_ready():
            return
        executable = installed_ollama()
        if not executable:
            raise RuntimeError('Ollama пока не найдена. Завершите установку и снова откройте START_LOCAL_AI.cmd.')
    print('Запускаю локальную ИИ-модель…', flush=True)
    log = open(STATE / 'ollama.log', 'a', encoding='utf-8')
    logs.append(log)
    process = subprocess.Popen([executable, 'serve'], stdout=log, stderr=log, env={**os.environ, 'OLLAMA_HOST':'127.0.0.1:11434'})
    children.append(process)
    for _ in range(60):
        if ollama_ready():
            return
        if process.poll() is not None:
            # The installed tray app may have won the startup race.
            time.sleep(.5)
            if ollama_ready():
                return
            break
        time.sleep(.5)
    raise RuntimeError('Не удалось запустить Ollama. Откройте её из меню Пуск и повторите запуск.')


def ensure_model():
    with request('/api/tags') as response:
        installed = json.load(response).get('models', [])
    if any(x.get('name') == MODEL or x.get('model') == MODEL for x in installed):
        return
    print('\nСкачиваю qwen3:4b (~2.5 ГБ), только при первом запуске.')
    print('Нужен интернет. Окно не закрывайте. Ctrl+C отменяет загрузку; её можно продолжить позже.', flush=True)
    last = None
    with request('/api/pull', {'model': MODEL, 'stream': True}, timeout=120) as response:
        succeeded = False
        for line in response:
            if not line.strip():
                continue
            event = json.loads(line)
            if event.get('error'):
                raise RuntimeError('Загрузка модели: ' + str(event['error']))
            total = event.get('total', 0)
            percent = int(100 * event.get('completed', 0) / total) if total else None
            label = str(event.get('status', 'Загрузка')) + (f' — {percent}%' if percent is not None else '')
            if label != last:
                print(label, flush=True)
                last = label
            if event.get('status') == 'success':
                succeeded = True
        if not succeeded:
            raise RuntimeError('Загрузка не завершилась. Проверьте интернет и запустите файл ещё раз.')


def warmup_model():
    print('\nПроверяю, что модель загружается на этом компьютере. Первый запуск может занять несколько минут…', flush=True)
    with request('/api/show', {'model': MODEL}, timeout=30) as response:
        details = json.load(response)
    if 'tools' not in details.get('capabilities', []):
        raise RuntimeError('Модель не объявляет поддержку tools. Обновите Ollama и повторите запуск.')
    with request('/api/chat', {
        'model': MODEL, 'messages': [{'role':'user','content':'Ответь одним словом: готово'}],
        'stream':False, 'think':False, 'keep_alive':'30m',
        'options': {'temperature':0, 'num_ctx':8192, 'num_predict':16}
    }, timeout=300) as response:
        data = json.load(response)
    if data.get('done') is not True or not data.get('message', {}).get('content'):
        raise RuntimeError('Модель не смогла ответить. Проверьте окно Ollama и свободную память компьютера.')


def wait_service(url, process):
    for _ in range(120):
        if process.poll() is not None:
            raise RuntimeError('Один из серверов завершился. Подробности находятся в папке .local-ai рядом с файлом запуска.')
        try:
            with HTTP.open(url, timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        time.sleep(.25)
    raise RuntimeError('Сервер не успел запуститься. Проверьте журнал в папке .local-ai.')


def main():
    os.chdir(ROOT)
    STATE.mkdir(exist_ok=True)
    children, logs = [], []
    print('HackAlem AI — запуск без API-ключа\n')
    print('Модель работает на вашем компьютере. Каталог: '+('реальная выборка ekt.kz' if os.environ.get('CATALOG_MODE')=='live' else 'демонстрационный'))
    try:
        occupied = busy_ports([8001,8002,3000])
        if occupied:
            raise RuntimeError('Заняты порты '+', '.join(map(str,occupied))+'. В старых трёх терминалах VS Code нажмите Ctrl+C, затем снова запустите этот файл. Чужие процессы автоматически не завершаются.')
        ensure_ollama(children, logs)
        ensure_model()
        warmup_model()
        python = ensure_python()
        # No cloud credentials; internal capability stays within these child processes.
        env = {**os.environ, 'PYTHONUTF8':'1', 'LLM_PROVIDER':'ollama', 'LLM_MODEL':MODEL,
               'OLLAMA_URL':OLLAMA, 'LLM_TIMEOUT':'180', 'ASSISTANT_TURN_TIMEOUT':'300',
               'CHAT_TIMEOUT_MS':'315000', 'INTERNAL_API_TOKEN':secrets.token_urlsafe(32),
               'CATALOG_SERVICE_URL':'http://127.0.0.1:8001',
               'PUBLIC_CATALOG_URL':'http://localhost:8001',
               'ASSISTANT_SERVICE_URL':'http://localhost:8002',
               'CORS_ORIGINS':'http://localhost:3000,http://127.0.0.1:3000'}
        env['CATALOG_MODE'] = os.environ.get('CATALOG_MODE','demo')
        env['CATALOG_DB'] = str(STATE / (env['CATALOG_MODE']+'.sqlite'))
        specifications = [
            ('catalog',[python,'-X','utf8','-m','uvicorn','catalog.api:app','--app-dir','catalog-service','--host','127.0.0.1','--port','8001'],'http://127.0.0.1:8001/health'),
            ('assistant',[python,'-X','utf8','-m','uvicorn','assistant.api:app','--app-dir','assistant-service','--host','127.0.0.1','--port','8002'],'http://127.0.0.1:8002/health'),
            ('widget',[python,'-X','utf8','chat-widget/server.py'],'http://127.0.0.1:3000/'),
        ]
        for name, command, url in specifications:
            print('Запускаю '+name+'…', flush=True)
            log = open(STATE/(name+'.log'),'a',encoding='utf-8'); logs.append(log)
            process = subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=log)
            children.append(process)
            wait_service(url,process)
        health=read_json('http://127.0.0.1:8002/health')
        if health.get('catalog_service_reachable') is not True:
            raise RuntimeError('Ассистент не видит каталог. Проверьте журналы в .local-ai.')
        print('\nСайт запущен: http://localhost:3000')
        print('Оставьте это окно открытым. Для завершения нажмите Ctrl+C.')
        print('В чате спросите: '+('Расскажи о товаре 200300285_, укажи цену, остаток и противоречия в характеристиках.' if env['CATALOG_MODE']=='live' else 'Есть ли DEMO-C16?'))
        print('Локальная модель может отвечать медленно; скорость зависит от компьютера.\n', flush=True)
        webbrowser.open('http://localhost:3000')
        while True:
            time.sleep(1)
            if any(process.poll() is not None for process in children[-3:]):
                raise RuntimeError('Один из серверов остановился. Проверьте журналы в .local-ai.')
    except KeyboardInterrupt:
        print('\nОстанавливаю процессы этого запуска…')
    except (OSError,ValueError,RuntimeError,subprocess.CalledProcessError) as exc:
        print('\nНе удалось завершить запуск: '+str(exc),flush=True)
        return 1
    finally:
        for process in reversed(children):
            if process.poll() is None:
                process.terminate()
        for process in children:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        for log in logs:
            log.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
