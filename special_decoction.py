#coding=utf-8

import RPi.GPIO as GPIO
import time
from general_decoction import *
from sys import argv

GPIO.setmode(GPIO.BOARD)

he_jinshui = 21
#jinpao_ENA = 24
jinpao_DIR = 26
jinpao_PUL = 32
#chuyao_ENA = 33
chuyao_DIR = 35
chuyao_PUL = 37
#guogai_ENA = 36
guogai_DIR = 38
guogai_PUL = 40

channel_list = [21,26,32,35,37,38,40]
GPIO.setup(channel_list,GPIO.OUT)

#浸泡盒进水
def jinshui_he(jinshui_time):
    GPIO.output(he_jinshui,GPIO.HIGH)
    time.sleep(jinshui_time)
    GPIO.output(he_jinshui,GPIO.LOW)

#定义电机类，翻转与复位
class motor(object):
    def __init__(self,name):
        self.name = name
        self.PUL = name + "_" + "PUL"
        self.DIR = name + "_" + "DIR"
    def run(self, fred, dc, runtime, direction):    #fred频率，dc占空比，runtime电机运行时间，dir方向
        p = GPIO.PWM(locals()[self.PUL],fred)
        p.start(dc)
        if direction == "HIGH":
            GPIO.output(locals()[self.DIR],GPIO.HIGH)
        elif direction == "LOW":
            GPIO.output(locals()[self.DIR],GPIO.LOW)
        time.sleep(runtime)
        p.stop()
        del p

def xianjian():
    global xj_time,tj_time,ej_time
    jinshui_guo(15)
    time.sleep(300)
    jinshui_he(10)  # 浸泡盒进水
    wuhuo()
    time.sleep(0.1)  # 延时等待留给系统空闲时间
    wenhuo(xj_time * 60)  # 结束先煎
    print("先煎结束，开始头煎")
    guogai_motor.run(500, 90, 0.6, "LOW")  # 锅盖电机开启
    time.sleep(0.1)
    jinpao_motor.run(2000, 60, 45, "HIGH")  # 浸泡盒电机翻转
    time.sleep(2)
    jinshui_he(3)  # 冲刷残留药材
    guogai_motor.run(500, 90, 0.5, "HIGH")  # 锅盖电机复位
    time.sleep(0.1)
    wuhuo()
    jinpao_motor.run(4000, 60, 27, "LOW")  # 浸泡盒电机复位
    time.sleep(1)
    if yao == "jiebiao":
        if tj_time < 10 or tj_time > 25:
            wenhuo(900)
        else:
            wenhuo(tj_time * 60)
    elif yao == "zibu":
        if tj_time < 25:
            wenhuo(1800)
        else:
            wenhuo(tj_time * 60)
    else:
        wenhuo(tj_time * 60)  # 结束头煎
    print("头煎完成，正在二煎")
    jinyao_hu()
    time.sleep(0.1)
    jinshui_guo(10)  # 进水量须再试验测试
    wuhuo()
    time.sleep(0.1)
    if yao == "jiebiao":
        if tj_time < 5 or tj_time > 15:
            wenhuo(600)
        else:
            wenhuo(ej_time * 60)
    elif yao == "zibu":
        if tj_time < 15:
            wenhuo(1500)
        else:
            wenhuo(ej_time * 60)
    else:
        wenhuo(ej_time * 60)  # 结束二煎
    time.sleep(0.1)
    print("二煎结束")

def liangjian():
    global tj_time,ej_time
    jinshui_guo(10)
    time.sleep(900)
    wuhuo()
    if yao == "jiebiao":
        if tj_time < 10 or tj_time > 25:
            wenhuo(900)
        else:
            wenhuo(tj_time * 60)
    elif yao == "zibu":
        if tj_time < 25:
            wenhuo(1800)
        else:
            wenhuo(tj_time * 60)
    else:
        wenhuo(tj_time * 60)  # 结束头煎
    #GPIO.output(guo_380w,GPIO.LOW)
    print("头煎完成，开始二煎。")
    #结束头煎
    time.sleep(0.01)#延时等待留给系统空闲时间
    jinyao_hu()
    time.sleep(0.01)
    jinshui_guo(10)
    wuhuo()
    time.sleep(0.1)
    if yao == "jiebiao":
        if tj_time < 5 or tj_time > 15:
            wenhuo(600)
        else:
            wenhuo(ej_time * 60)
    elif yao == "zibu":
        if tj_time < 15:
            wenhuo(1500)
        else:
            wenhuo(ej_time * 60)
    else:
        wenhuo(ej_time * 60)  # 结束二煎
    print("两煎结束")

def houxia():
    global hx_time
    guogai_motor.run(500, 90, 0.6, "LOW")  # 锅盖电机开启
    time.sleep(0.1)
    chuyao_motor.run(490, 78, 4.8, "LOW")  # 储药盒电机翻转
    time.sleep(5)
    guogai_motor.run(500, 90, 0.5, "HIGH")  # 锅盖电机复位
    time.sleep(0.1)
    chuyao_motor.run(490, 78, 4.8, "HIGH")  # 储药盒电机复位
    wenhuo(hx_time*60)  # 煎煮后下药（三煎文火）

#一、煎锅进水（先煎药药量少吸水性差，进水少许），二、煎锅浸泡15分钟，三、浸泡盒进水（浸泡共煎药）
#四、先煎武火（加热至水沸腾）五、先煎文火5min六、停止加热，打开锅盖七、浸泡盒翻转
#八、浸泡盒进水5s，（冲刷残留在浸泡盒里的药材）九、关闭锅盖，十、浸泡盒复位，十一、头煎武火（加热至水沸腾）
#十二、头煎文火（解表十五分钟，调理滋补三十分钟，其他药二十五分钟）十三、吸取头煎药液十四、煎锅进水（少）
#十五、二煎武火（加热至水沸腾）十六、二煎文火（解表十分钟，调理滋补二十五分钟，其他药二十分钟）
#十七、停止加热，打开锅盖十八、储药盒翻转十九、关闭锅盖二十、储药盒复位二十一、三煎文火4min
#二十二、吸取三煎后的药液二十三、药液壶保温
def main():
    guogai_motor = motor("guogai")
    jinpao_motor = motor("jinpao")
    chuyao_motor = motor("chuyao")    #创建三个电机对象
    yao = argv[1]
    xj_time = argv[2]
    tj_time = argv[3]
    ej_time = argv[4]
    hx_time = argv[5]    #接收煎药模式和煎药时间
    if xj_time > 0 and hx_time == 0 :
        xianjian()    #先煎模式（包括：先煎，头煎，二煎）
    if xj_time > 0 and hx_time >0:
        xianjian()
        houxia()     #先煎+后下模式（包括：先煎，头煎，二煎，后下）
    if xj_time == 0 and hx_time > 0:
        liangjian()
        houxia()    #后下模式（包括：头煎，二煎，后下）
    if xj_time + hx_time == 0:
        liangjian()    #两煎模式（包括头煎，二煎）
    time.sleep(5)
    jinyao_hu()
    time.sleep(0.1)
    baowen_hu()    #药液壶开启保温等待饮用
    GPIO.cleanup()
    print("谢谢使用，祝您早日康复！")


if __name__ == '__main__':
    main()

