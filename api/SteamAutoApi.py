import sys
import threading
import time

from flask_socketio import SocketIO

from flask import Flask
import Result
import Steamauto
import utils.tools as tools
from plugins.BuffAutoAcceptOffer import BuffAutoAcceptOffer
from plugins.BuffAutoOnSale import BuffAutoOnSale
from plugins.SteamAutoAcceptOffer import SteamAutoAcceptOffer
from plugins.UUAutoAcceptOffer import UUAutoAcceptOffer
from utils.logger import logger

app = Flask(__name__)
socketio = SocketIO()
socketio.init_app(app, cors_allowed_origins='*')

global steam_client, steam_client_mutex


@app.get('/login')
def login(): pass


@app.get('/init_files_and_params')
def init_files_and_params():
    # 文件缺失或格式错误返回0，首次运行返回1，非首次运行返回2
    init_status = Steamauto.init_files_and_params()
    if init_status == 0:
        tools.pause()
        return Result.Result(init_status, 'files_missing_or_format_error').to_json()
    elif init_status == 1:
        tools.pause()
        return Result.Result(init_status, 'first_run').to_json()
    elif init_status == 2:
        return Result.Result(init_status, 'not_first_run').to_json()
    return Result.Result(-1, 'unknown_error').to_json()


@app.get("/steam_login")
def steam_login():
    global steam_client, steam_client_mutex
    steam_client = Steamauto.login_to_steam()
    if steam_client is None:
        return Result.Result(1, '登录失败').to_json()
    steam_client_mutex = threading.Lock()
    # 仅用于获取启用的插件
    plugins_enabled = Steamauto.get_plugins_enabled(steam_client, steam_client_mutex)
    # 检查插件是否正确初始化
    plugins_check_status = Steamauto.plugins_check(plugins_enabled)
    if plugins_check_status == 0:
        logger.info("存在插件首次运行, 请按照README提示填写配置文件! ")
        tools.pause()
        return Result.Result(2, '存在插件首次运行').to_json()

    if steam_client is not None:
        return Result.Result(0, '登录成功').to_json()


@socketio.on('connect', namespace='/start_task')
def init_plugins_and_start_task():
    global steam_client, steam_client_mutex
    plugins_enabled = Steamauto.get_plugins_enabled(steam_client, steam_client_mutex)
    logger.info("初始化完成, 开始运行插件!")
    SocketIO.send(socketio, Result.Result(0, '初始化完成, 开始运行插件!').to_json(), namespace='/start_task')
    print("\n")
    time.sleep(0.1)
    if len(plugins_enabled) == 1:
        tools.exit_code.set(plugins_enabled[0].exec())
    else:
        threads = []
        for plugin in plugins_enabled:
            threads.append(threading.Thread(target=plugin.exec))
        for thread in threads:
            thread.daemon = True
            thread.start()
        for thread in threads:
            thread.join()
    if tools.exit_code.get() != 0:
        logger.warning("所有插件都已经退出！这不是一个正常情况，请检查配置文件.")
        SocketIO.send(socketio, Result.Result(-2, '所有插件都已经退出！这不是一个正常情况，请检查配置文件.').to_json(), namespace='/start_task')

    logger.info("由于所有插件已经关闭,程序即将退出...")
    SocketIO.send(socketio, Result.Result(-1, '由于所有插件已经关闭,程序即将退出...').to_json(), namespace='/start_task')
    tools.pause()
    sys.exit(tools.exit_code.get())


@socketio.on('disconnect', namespace='/stop_task')
def stop_task():
    tools.pause()
    sys.exit(tools.exit_code.get())


def get_plugins_enabled():
    global config
    plugins_enabled = []
    if (
        "buff_auto_accept_offer" in config
        and "enable" in config["buff_auto_accept_offer"]
        and config["buff_auto_accept_offer"]["enable"]
    ):
        buff_auto_accept_offer = BuffAutoAcceptOffer(logger, steam_client, steam_client_mutex, config)
        plugins_enabled.append(buff_auto_accept_offer)
    if "buff_auto_on_sale" in config and "enable" in config["buff_auto_on_sale"] and config["buff_auto_on_sale"]["enable"]:
        buff_auto_on_sale = BuffAutoOnSale(logger, steam_client, steam_client_mutex, config)
        plugins_enabled.append(buff_auto_on_sale)
    if (
        "uu_auto_accept_offer" in config
        and "enable" in config["uu_auto_accept_offer"]
        and config["uu_auto_accept_offer"]["enable"]
    ):
        uu_auto_accept_offer = UUAutoAcceptOffer(logger, steam_client, steam_client_mutex, config)
        plugins_enabled.append(uu_auto_accept_offer)
    if (
        "steam_auto_accept_offer" in config
        and "enable" in config["steam_auto_accept_offer"]
        and config["steam_auto_accept_offer"]["enable"]
    ):
        steam_auto_accept_offer = SteamAutoAcceptOffer(logger, steam_client, steam_client_mutex, config)
        plugins_enabled.append(steam_auto_accept_offer)

    return plugins_enabled


if __name__ == '__main__':
    socketio.run(app, debug=True, host='127.0.0.1', port=11000)
