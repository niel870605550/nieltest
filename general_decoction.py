#coding=utf-8

__all__ = ["read_temp","jinshui_guo","wuhuo","wenhuo","jinyao_hu","baowen_hu"]

import time
import os
import glob
from sys import argv
import RPi.GPIO as GPIO

GPIO.setmode(GPIO.BOARD)

#温度传感器数据读取
def read_temp(flag):
    os.system('modprobe w1-gpio')
    os.system('modprobe w1-therm')
    device_guo = '/sys/bus/w1/devices/28-0417a2f0f6ff/w1_slave'
    #device_hu = '/sys/bus/w1/devices/28-0417a2f0f6ff/w1_slave'
    if flag == 1:
        device_file = device_guo
    else:
        pass
        #device_file = device_hu
    f = open(device_file,'r')
    lines = f.readlines()
    f.close()
    equals_pos = lines[1].find('t=')
    if equals_pos != -1:
        temp_string = lines[1][equals_pos+2:]
        temp = float(temp_string)/1000.0
        return temp

#定义各个接口
guo_jinshui = 19
guo_380w = 16
guo_220w = 18
hu_100w = 22
hu_jinyao = 23
shuiwei_guo = 11
shuiwei_hu = 13

#接口模式设置
GPIO.setup(guo_jinshui,GPIO.OUT)
GPIO.setup(guo_380w,GPIO.OUT)
GPIO.setup(guo_220w,GPIO.OUT)
GPIO.setup(hu_jinyao,GPIO.OUT)
GPIO.setup(hu_100w,GPIO.OUT)
GPIO.setup(shuiwei_guo,GPIO.IN)
GPIO.setup(shuiwei_hu,GPIO.IN)
GPIO.setup(shuiwei_guo,GPIO.IN,pull_up_down=GPIO.PUD_UP)
GPIO.setup(shuiwei_hu,GPIO.IN,pull_up_down=GPIO.PUD_UP)

#煎锅进水
def jinshui_guo(jinshui_time):
    GPIO.output(guo_jinshui,GPIO.HIGH)
    time.sleep(jinshui_time)
    GPIO.output(guo_jinshui,GPIO.LOW)

#武火加热
def wuhuo():
    GPIO.output(guo_380w,GPIO.HIGH)
    GPIO.output(guo_220w,GPIO.HIGH)
    temp = read_temp(1)
    t = int((temp-8.785)/0.107)
    time.sleep(900-t)
    while True:
        t = read_temp(1)
        if t >= 98.5:
            GPIO.output(guo_220w,GPIO.LOW)
            GPIO.output(guo_380w,GPIO.LOW)
            break
        time.sleep(5)

#文火加热（液位传感防止溢锅）
def wenhuo(wenhuo_time):
    GPIO.output(guo_380w,GPIO.HIGH)
    i=0
    while wenhuo_time>0:
        if i == 0:
        #if GPIO.input(shuiwei_guo) == 0#煎锅液位过高，可能会溢出
            GPIO.output(guo_380w,GPIO.LOW)
            time.sleep(10)
            GPIO.output(guo_380w,GPIO.HIGH)
            i=1
        else:
            i=0
        time.sleep(5)
        wenhuo_time=wenhuo_time-5-(10*i)
    GPIO.output(guo_380w,GPIO.LOW)

#吸取药液
def jinyao_hu():
    GPIO.output(hu_jinyao,GPIO.HIGH)
    time.sleep(30)
    GPIO.output(hu_jinyao,GPIO.LOW)
    
#药液壶保温
def baowen_hu():
    while True:
        t = read_temp(2)
        if GPIO.input(shuiwei_hu) == 0:#药液壶液位较低（既药液已被饮用）
            GPIO.output(hu_100w,GPIO.LOW)
            break
        if t<45 and t<60:
            GPIO.output(hu_100w,GPIO.HIGH)
        else:
            GPIO.output(hu_100w,GPIO.LOW)
        time.sleep(60)
        print("煎煮完成，请您及时饮用。")

def main():
#一，煎锅进水
#二，浸泡二十分钟
#三，头煎武火（加热至水沸腾）
#四，头煎文火（解表药十五分钟，调理滋补药三十分钟，其他药二十五分钟）
#五，吸取头煎药液
#六，煎锅进水
#七，二煎武火（加热至水沸腾）
#八，二煎文火（解表药十分钟，调理滋补药二十五分钟，其他药二十分钟）
#九，吸取二煎药液
#十，药液壶保温
    jinshui_guo(20)
    time.sleep(900)
    wuhuo()
    time.sleep(1)
    try:
        yao = sys.argv[1]
    except IndexError:
        yao = "yiban"
    if yao == "jiebiao":
        wenhuo(900)
    elif yao == "zibu":
        wenhuo(1800)
    else:
        wenhuo(1500)
    #GPIO.output(guo_380w,GPIO.LOW)
    #结束头煎
    print("头煎完成，开始二煎")
    time.sleep(0.01)#延时等待留给系统空闲时间 
    jinyao_hu()
    time.sleep(0.01)
    jinshui_guo(15)
    wuhuo()
    time.sleep(0.1)
    if yao == "jiebiao":
        wenhuo(600)
    elif yao == "zibu":
        wenhuo(1500)
    else:
        wenhuo(1200)
    #GPIO.output(guo_380w,GPIO.LOW)
    #二煎结束
    print("二煎完成")
    time.sleep(5) 
    jinyao_hu()
    time.sleep(0.01)
    baowen_hu()#药液壶开启保温等待饮用
    GPIO.cleanup()
    print("谢谢使用，祝您早日康复")

if __name__ == '__main__':
    main()
