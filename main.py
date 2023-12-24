import network
import utime
from micropyserver import MicroPyServer
import utils
from umqtt.simple import MQTTClient
import machine
from utils import log
import json
from machine import Pin, ADC, SoftI2C
import ssd1306
import time

# 1. connect wifi


def release_wifi():
    sta_if = network.WLAN(network.STA_IF)

    if sta_if.isconnected():
        sta_if.disconnect()
        log("Disconnected from Wi-Fi network.", "INFO")

    sta_if.active(False)
    log("STA interface disabled. Wi-Fi cache released.", "INFO")


def connect_wifi(wifi_name, wifi_password):
    global wifi_wait_time
    wifi_connect = False
    sta_if = network.WLAN(network.STA_IF)

    # call the function to release Wi-Fi cache
    release_wifi()
    if not sta_if.isconnected():
        try:
            sta_if.active(True)
            sta_if.connect(wifi_name, wifi_password)
            while not sta_if.isconnected():
                utime.sleep(1)

                wifi_wait_time += 1
                if wifi_wait_time >= 10:
                    raise Exception("Connection timeout")

            wifi_connect = True

            log("Connected to Wi-Fi network.", "INFO")
            log("Network config: {}".format(sta_if.ifconfig()), "INFO")
        except Exception as e:
            log("Failed to connect to Wi-Fi network: {}".format(e), "ERROR")
            log("Network config: {}".format(sta_if.ifconfig()), "INFO")
            wifi_connect = False
    return wifi_connect


# 2. connect mqtt
# 2.1 add route to be checked


def restart_and_reconnect():
    print("Failed to connect to MQTT broker. Reconnecting...")
    utime.sleep(10)
    machine.reset()


def connect_and_subscribe(clientID, myTopic):
    try:
        client = MQTTClient(
            client_id=clientID, server=serverIP, port=port, keepalive=6000
        )
        client.set_callback(MsgOK)
        client.connect()
        client.subscribe(myTopic)
        log("Connected to MQTT server at {}:{}".format(serverIP, port), "INFO")
        return client
    except Exception as e:
        log("Failed to connect to MQTT server: " + str(e), "ERROR")
        restart_and_reconnect()


def connect_show_params(client, request):
    global mqtt_client
    global run
    global serverIP
    global port
    global machineId
    global server
    global clientID
    global myTopic

    """ request handler """
    params = utils.get_request_query_params(request)
    log("connect show params: {}".format(params))
    ips = params["mqtt_ip"].split(":")
    serverIP = ips[0]
    port = ips[1]
    """ will return {"param_one": "one", "param_two": "two"} """
    server.send(client, "HTTP/1.0 200 OK\r\n")
    server.send(client, "Content-Type: text/html\r\n\r\n")
    if machineId != params["machineid"]:
        return server.send(client, "Not this car")
    if run == True:
        return server.send(client, "mqtt is connected!")
    try:
        mqtt_client = connect_and_subscribe(clientID, myTopic)
        server.send(client, "ok")
        run = True
        # server.stop()
    except OSError as e:
        server.send(client, "failed")


def stop_show_params(client, request):
    global mqtt_client
    global run
    global machineId
    """ request handler """
    params = utils.get_request_query_params(request)
    print(params)
    server.send(client, "HTTP/1.0 200 OK\r\n")
    server.send(client, "Content-Type: text/html\r\n\r\n")
    if machineId != params["machineid"]:
        return server.send(client, "Not this car")
    if run != True:
        return server.send(client, "No mqtt connected!")
    try:
        mqtt_client.disconnect()
        server.send(client, "ok")
        run = False
    except OSError as e:
        server.send(client, "failed")


def status_show_params(client, request):
    global run, serverIP, port, machineId, server
    """ request handler """
    params = utils.get_request_query_params(request)
    print(params)
    if machineId != params["machineid"]:
        server.send(client, "HTTP/1.0 200 OK\r\n")
        server.send(client, "Content-Type: text/html\r\n\r\n")
        return server.send(client, "Not this car")
    json_str = json.dumps({"run": run, "mqtt_ip": "{}:{}".format(serverIP, port)})
    server.send(client, "HTTP/1.0 200 OK\r\n")
    server.send(client, "Content-Type: application/json\r\n\r\n")
    server.send(client, json_str)

def MsgOK(topic, msg):
    global mqtt_client
    log("Received message: {} on topic: {}".format(msg, topic), "INFO")


# 更新屏幕
def update_screen(
    device_name,
    device_name_mode="display",
    device_name_edit_current_index=0,
):
    global mqtt_client
    global serverIP
    global port
    global wifi_connect

    oled.fill(0)
    if device_name_mode == "edit":
        oled.text("Edit device id", 0, 0)
        oled.text(" " * device_name_edit_current_index + "-", 0, 15)

    else:
        oled.text("Device id", 0, 0)

    oled.text(device_name, 0, 8)

    if not wifi_connect:
        oled.text("wait for wifi", 0, 20)
    elif not mqtt_client:
        oled.text("wait for server", 0, 20)
    else:
        oled.text(serverIP, 0, 20)

    oled.show()


# 更新屏幕

"""
    default status:
    L: unpressed: 1, pressed: 0
    R: unpressed: 1, pressed: 0

    X: middle: 2800 < y < 3000, left: 3000 < y , right: y < 1500
    Y: middle: 2800 < x < 3000, up: 3000 < x , down: x < 1500

    A: pressed: 2100 < ABCD < 2800
    B: pressed: ABCD < 70
    C: pressed: 2800 < ABCD < 3500
    D: pressed: 600 < ABCD < 1000

"""


def get_X_status(x, y):
    if y > 3000:
        return "left"
    elif y < 1500:
        return "right"
    else:
        return "middle"


def get_Y_status(x, y):
    if x > 3000:
        return "forward"
    elif x < 1500:
        return "backward"
    else:
        return "middle"


def get_ABCD_status(abcd):
    if abcd > 2100 and abcd < 2800:
        return "A"
    elif abcd < 70:
        return "B"
    elif abcd > 2800 and abcd < 3500:
        return "C"
    elif abcd > 600 and abcd < 1000:
        return "D"
    else:
        return "None"


def get_display_edit_name(display_edit_name, display_edit_name_current_index, up_down):
    display_alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"

    if up_down == "forward":
        current_char = display_edit_name[display_edit_name_current_index - 1]
        current_char_index = display_alphabet.index(current_char)
        if current_char_index == 0:
            current_char = display_alphabet[-1]
        else:
            current_char = display_alphabet[current_char_index - 1]
    else:
        current_char = display_edit_name[display_edit_name_current_index - 1]
        current_char_index = display_alphabet.index(current_char)
        if current_char_index == len(display_alphabet) - 1:
            current_char = display_alphabet[0]
        else:
            current_char = display_alphabet[current_char_index + 1]
    return (
        display_edit_name[: display_edit_name_current_index - 1]
        + current_char
        + display_edit_name[display_edit_name_current_index:]
    )


if __name__ == "__main__":
    wifi_wait_time = 0

    # MQTT setting
    myTopic = "joystick"
    clientID = "joystick"

    run = False
    serverIP = "192.168.123.166"
    port = 1883

    machineId = "joystick"

    mqtt_client = False
    mqtt_client_connect_count = 0

    wifi_connect = False
    wifiName = ""
    wifiPassword = ""

    # screen init
    i2c = SoftI2C(scl=Pin(5), sda=Pin(4))
    oled = ssd1306.SSD1306_I2C(128, 32, i2c)

    wifi_connect = connect_wifi(wifiName, wifiPassword)
    server = MicroPyServer()

    server.add_route("/connect", connect_show_params)
    server.add_route("/stop", stop_show_params)
    server.add_route("/status", status_show_params)
    server.stop()
    server.start()
    """

    """

    pin_ABCD = ADC(Pin(0))
    pin_Y = ADC(Pin(1))
    pin_X = ADC(Pin(3))
    pin_ABCD.atten(ADC.ATTN_11DB)
    pin_Y.atten(ADC.ATTN_11DB)
    pin_X.atten(ADC.ATTN_11DB)

    pin_L = Pin(8, Pin.IN)
    pin_R = Pin(10, Pin.IN)

    L_status = ["pressed", "unpressed"]
    R_status = ["pressed", "unpressed"]

    """
    1. screen init as menu
    """
    display_setting_1 = ["home", "edit"]
    display_current_device_id = "car1"
    display_state = "display"
    display_device_name = "car1"
    display_edit_name_current_index = len(display_device_name)
    display_edit_name = display_device_name

    update_screen(display_device_name)

    while True:
        server.loop()

        if mqtt_client:
            # mqtt_client.publish(myTopic, "hello world, this is joystick")
            mqtt_client.check_msg()
            if mqtt_client_connect_count == 0:
                update_screen(display_device_name)
                mqtt_client_connect_count += 1

            ABCD = get_ABCD_status(pin_ABCD.read())
            Y = get_Y_status(pin_X.read(), pin_Y.read())
            X = get_X_status(pin_X.read(), pin_Y.read())
            L = L_status[pin_L.value()]
            R = L_status[pin_R.value()]
            print("ABCD: %s, Y: %s, X: %s, L: %s, R: %s" % (ABCD, Y, X, L, R))
            print("display_state: %s" % display_state)
            if display_state == "display":
                if L == "pressed" and R == "pressed":
                    display_state = "set"
                    update_screen(
                        display_device_name, "edit", display_edit_name_current_index - 1
                    )
                    utime.sleep(1)
                    # print all button status
                if Y != "middle":
                    mqtt_client.publish(display_device_name, Y)
                if X != "middle":
                    mqtt_client.publish(display_device_name, X)
                if ABCD != "None":
                    mqtt_client.publish(display_device_name, ABCD)

            elif display_state == "set":
                # display_edit_name = display_device_name
                # B 或者LR同时按确定提交修改，device_name = edit_name，退出模式，D 删除，current_edit_index位置删除字符，C 取消，推出模式
                if L == "pressed" and R == "pressed":
                    display_device_name = display_edit_name
                    display_state = "display"
                    update_screen(display_device_name)
                    utime.sleep(1)
                if ABCD == "B":
                    display_device_name = display_edit_name
                    display_state = "display"
                    update_screen(display_device_name)
                if ABCD == "C":
                    display_state = "display"
                    update_screen(display_device_name)
                if ABCD == "D":
                    display_edit_name = (
                        display_edit_name[: display_edit_name_current_index - 1]
                        + display_edit_name[display_edit_name_current_index:]
                    )
                    display_edit_name_current_index -= 1
                    update_screen(
                        display_edit_name, "edit", display_edit_name_current_index - 1
                    )
                if Y == "forward":
                    display_edit_name = get_display_edit_name(
                        display_edit_name, display_edit_name_current_index, "forward"
                    )

                    update_screen(
                        display_edit_name, "edit", display_edit_name_current_index - 1
                    )
                if Y == "backward":
                    display_edit_name = get_display_edit_name(
                        display_edit_name, display_edit_name_current_index, "backward"
                    )
                    update_screen(
                        display_edit_name, "edit", display_edit_name_current_index - 1
                    )
                if X == "left":
                    if display_edit_name_current_index > 1:
                        display_edit_name_current_index -= 1
                    else:
                        display_edit_name_current_index = len(display_edit_name)
                    update_screen(
                        display_edit_name, "edit", display_edit_name_current_index - 1
                    )
                if X == "right":
                    if display_edit_name_current_index < len(display_edit_name):
                        display_edit_name_current_index += 1
                    else:
                        # display_edit_name最后加一个字符a
                        display_edit_name += "a"
                        display_edit_name_current_index += 1
                    update_screen(
                        display_edit_name, "edit", display_edit_name_current_index - 1
                    )

        utime.sleep(0.5)
    server.stop()
