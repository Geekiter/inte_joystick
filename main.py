import network
import utime
from micropyserver import MicroPyServer
import utils
from umqtt.simple import MQTTClient
import machine
from utils import log
import json
from machine import Pin, ADC
import time
# 1. connect wifi



def release_wifi():
    sta_if = network.WLAN(network.STA_IF)

    if sta_if.isconnected():
        # 如果已连接，先断开连接
        sta_if.disconnect()
        log("Disconnected from Wi-Fi network.", "INFO")

    # 禁用STA接口
    sta_if.active(False)
    log("STA interface disabled. Wi-Fi cache released.", "INFO")


def connect_wifi(wifi_name, wifi_password):
    global wifi_wait_time
    wifi_connect = False
    sta_if = network.WLAN(network.STA_IF)

    # 调用释放Wi-Fi缓存的函数
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
    print('Failed to connect to MQTT broker. Reconnecting...')
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
    ''' request handler '''
    params = utils.get_request_query_params(request)
    print(params)
    server.send(client, "HTTP/1.0 200 OK\r\n")
    server.send(client, "Content-Type: text/html\r\n\r\n")
    if machineId != params['machineid']:
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
    ''' request handler '''
    params = utils.get_request_query_params(request)
    print(params)
    if machineId != params['machineid']:
        server.send(client, "HTTP/1.0 200 OK\r\n")
        server.send(client, "Content-Type: text/html\r\n\r\n")
        return server.send(client, "Not this car")
    json_str = json.dumps(
        {"run": run, "mqtt_ip": "{}:{}".format(serverIP, port)})
    server.send(client, "HTTP/1.0 200 OK\r\n")
    server.send(client, "Content-Type: application/json\r\n\r\n")
    server.send(client, json_str)

# 3. subscribe topic
# 4. publish message to topic
def MsgOK(topic, msg):         
    global mqtt_client
    log("Received message: {} on topic: {}".format(msg, topic), 'INFO')

if __name__ == "__main__":
    
    wifi_wait_time = 0

    # MQTT setting
    myTopic = "joystick"
    clientID = "joystick"

    run = False
    serverIP = ""
    port = 1883

    machineId = "joystick"

    mqtt_client = False

    wifiName = ""
    wifiPassword = ""
    wifi_connect = connect_wifi(wifiName, wifiPassword)

    server = MicroPyServer()

    server.add_route("/connect", connect_show_params)
    server.add_route("/stop", stop_show_params)
    server.add_route("/status", status_show_params)
    server.stop()
    server.start()
    """

    """
    #IO0 属于ADC还是GPIO？ ADC1_CH0
    pin_ABCD = ADC(Pin(0))
    pin_Y = ADC(Pin(1))
    pin_X = ADC(Pin(3))
    pin_ABCD.atten(ADC.ATTN_11DB)
    pin_Y.atten(ADC.ATTN_11DB)
    pin_X.atten(ADC.ATTN_11DB)

    pin_L = Pin(8, Pin.IN)
    pin_R = Pin(10, Pin.IN)
    pin_I = Pin(18, Pin.IN)

    ABDC_status = "A"
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
    L_status = ["pressed", "unpressed"]
    R_status = ["pressed", "unpressed"]


    # pin_I = Pin(18, Pin.IN)


    while True:
        # 读取所有的按键状态


        server.loop()
        if mqtt_client:
            # mqtt_client.publish(myTopic, "hello world, this is joystick")
            mqtt_client.check_msg()

            ABCD = pin_ABCD.read()
            Y = pin_Y.read()
            X = pin_X.read()
            
            L = pin_L.value()
            R = pin_R.value()
            # I = pin_I.value()

            # 打印所有按键的状态
            print("ABCD: %d, Y: %d, X: %d, L: %d, R: %d" % (ABCD, Y, X, L, R))
            if L_status[L] == "pressed":
                mqtt_client.publish(myTopic, "L pressed")
            

        utime.sleep(1)
    server.stop()
    
        
        
    



