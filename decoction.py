#coding=utf-8

import re
import random
import os
import time
import socket
import struct
import json
import threading
import RPi.GPIO as GPIO
from general_decoction import read_temp
from queue import Queue

#定义消息类型
CONN_REQ = 0x10    #建立连接请求
CONN_RESP = 0x20   #连接建立响应
PUSH_DATA = 0x30   #转发（透传）数据
CONN_CLOSE = 0x40  #连接关闭
SAVE_DATA = 0x80   #存储（&转发）数据
SAVE_ACK = 0x90    #存储确认
CMD_REQ = 0xa0     #命令请求
CMD_RESP = 0xb0    #命令响应
PING_REQ = 0xc0    #心跳请求
PING_RESP = 0xd0   #心跳响应

ProductID = 142061 #产品ID
AuthInfo = "hahah" #鉴权信息

class client:
    def __init__(self,name=None):
        self.clientSocket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.name = name
        self.recvdata = None

    #计算消息剩余长度
    def _RemaLen(self,MsgType,len1,len2=0):
        if MsgType == CONN_REQ:
            digit = 15 + len1 +len2
        elif MsgType == SAVE_DATA:
            digit = 8 + len1 + len2
        RLen_high = digit % 128
        RLen_low = digit // 128
        if RLen_low > 0:
            RLen_high = RLen_high | 0x80
            RLen = RLen_high * 16 + RLen_low
            RLen_bytes = 2
        else:
            RLen = RLen_high
            RLen_bytes = 1
        return RLen,RLen_bytes

    #与oneNET建立连接
    def connect(self,ProductID,AuthInfo):
        self.clientSocket.connect(("jjfaedp.hedevice.com", 876))
        lenPID = len(str(ProductID))    #产品ID长度
        lenPID_high = (lenPID & 0xff00) >> 2    #产品ID长度高位
        lenPID_low = lenPID & 0x00ff    #产品ID长度低位
        lenAInfo = len(AuthInfo)    #鉴权信息长度
        lenAInfo_high = (lenAInfo & 0xff00) >> 2    #鉴权信息长度高位
        lenAInfo_low = lenAInfo & 0x00ff    #鉴权信息长度低位
        data_PID = (str(ProductID)).encode('ascii')    #产品ID字节串
        data_AInfo = AuthInfo.encode('ascii')    #鉴权信息字节串
        data_RLen,data_RLen_bytes = self._RemaLen(CONN_REQ,lenPID,lenAInfo)    #剩余消息长度重编码
        if data_RLen_bytes == 2:
            RLen_bytes_fmt = '!H'
        else:
            RLen_bytes_fmt = '!B'
        data_temp = struct.pack('!B',CONN_REQ)+struct.pack(RLen_bytes_fmt,data_RLen)+struct.pack('!H',0x0003)\
                    +'EDP'.encode('ascii')+bytes().fromhex('01c0012c0000')+struct.pack('!B',lenPID_high)\
                    +struct.pack('!B',lenPID_low)+data_PID+struct.pack('!B',lenAInfo_high)\
                    +struct.pack('!B',lenAInfo_low)+data_AInfo
        self.clientSocket.send(data_temp)
        recvData = self.clientSocket.recv(1024)
        data, = struct.unpack('!I', recvData)
        print("recvData:%s" % hex(data))
        ctime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        if data == 0x20020000:
            print("时间：%s\n设备：%s\n状态：已连接"%(ctime,self.name))
        else:
            print("设备：null\n状态：接入失败！请重新连接")
        #time.sleep(400)
        #self.clientSocket.close()

    #心跳请求
    def ping(self):
        while True:
            time.sleep(120)
            ping_data = struct.pack('!H', 0xc000)
            #mutex.acquire()
            self.clientSocket.send(ping_data)
            #mutex.release()

    #向云平台进行数据发送，平台会自动保存，并转发给DeviceID这个设备若无不转发，data格式{"temp":80},MsgNum取值：0-65535
    def savedata(self,data,MsgNum,DeviceID=None):
        self.saveData = data
        self.msgNum = MsgNum
        jsondata = json.dumps(data)
        lenjs = len(jsondata)
        data_jsondata = jsondata.encode('ascii')
        data_MsgNum = struct.pack('!H', MsgNum)  # 消息编号字节串
        if DeviceID == None:
            data_RLen, data_RLen_bytes = self._RemaLen(SAVE_DATA,lenjs)  # 剩余消息长度重编码
            data_RLen = data_RLen - 2
            if data_RLen_bytes == 2:
                RLen_bytes_fmt = '!H'
            else:
                RLen_bytes_fmt = '!B'
            data_temp = struct.pack('!B', SAVE_DATA) + struct.pack(RLen_bytes_fmt, data_RLen) + struct.pack('!B',0x40)\
                        + data_MsgNum + struct.pack('!B', 0x03) + struct.pack('!H',lenjs) + data_jsondata
            self.clientSocket.send(data_temp)
        else:
            lenDID = len(str(DeviceID))
            data_DID = (str(DeviceID)).encode('ascii')  # 设备ID字节串
            data_RLen, data_RLen_bytes = self._RemaLen(SAVE_DATA, lenDID, lenjs)  # 剩余消息长度重编码
            if data_RLen_bytes == 2:
                RLen_bytes_fmt = '!H'
            else:
                RLen_bytes_fmt = '!B'
            data_temp = struct.pack('!B', SAVE_DATA) + struct.pack(RLen_bytes_fmt, data_RLen) + struct.pack('!B',0xc0) \
                        + struct.pack('!H',lenDID) + data_DID + data_MsgNum + struct.pack('!B', 0x03)\
                        + struct.pack('!H',lenjs) + data_jsondata
            self.clientSocket.send(data_temp)

    #剩余消息长度解码
    def _LenDecond(self,byte1,byte2):
        multiplier = 128
        if byte1 & 0x80 == 0:
            byte = 1
            value = byte1
        else:
            value = byte2 & 0x7f
            value = value*multiplier + (byte1 & 0x7f)
            byte = 2
        return byte,value

    #接收OneNET的各种应答或者命令请求或者是别的设备转发的数据(返回命令字符串commandMsg或者数据字符串DataMsg)
    def recvDataAnalysis(self):
        global queue, queuedata
        while True:
            self.recvdata = self.clientSocket.recv(1024)
            flags = self.recvdata[0]
            if flags == PING_RESP:
                data, = struct.unpack('!H', self.recvdata)
                ctime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                if data == 0xd000:
                    print("时间：%s\n状态：%s保持连接" % (ctime, self.name))
                else:
                    print("时间：%s\n状态：%s已断开，请检查网络！" % (ctime, self.name))
            elif flags == SAVE_ACK:
                try:
                    data1, data2, data3, data4, data5 = struct.unpack('!3BHB', self.recvdata)
                    if data4 == self.msgNum:
                        print("%s已上传至OneNET" % (self.saveData))
                    else:
                        print("%s丢失" % (self.saveData))
                except Exception:
                    pass
            else:
                byte, commandlen = self._LenDecond(self.recvdata[1], self.recvdata[2])
            if flags == CMD_REQ:
                lenCID, = struct.unpack('!H', self.recvdata[(byte + 1):(byte + 3)])
                commandID_bytes, = struct.unpack('!%ds' % (lenCID), self.recvdata[(3 + byte):(3 + byte + lenCID)])
                commandID = commandID_bytes.decode('ascii')  # 解析命令ID
                lenCommandMsg, = struct.unpack('!I', self.recvdata[(3 + byte + lenCID):(7 + byte + lenCID)])
                commangMsg_bytes, = struct.unpack('!%ds' % (lenCommandMsg), self.recvdata[(7 + byte + lenCID):(
                7 + byte + lenCID + lenCommandMsg)])
                commangMsg = commangMsg_bytes.decode('ascii')  # 解析命令体
                print("收到设备云指令：%s（命令编号：%s）" % (commangMsg, commandID))
                #command = command + commangMsg
                queuedata = commangMsg
                queue.put(queuedata)
            elif flags == SAVE_DATA:
                dataMark = self.recvdata[(1 + byte)]
                if dataMark == 0xc0:
                    lenForwardAddr, = struct.unpack('!H', self.recvdata[(byte + 2):(byte + 4)])
                    ForwardAddr_bytes, = struct.unpack('!%ds' % (lenForwardAddr),
                                                       self.recvdata[(4 + byte):(4 + byte + lenForwardAddr)])
                    ForwardAddr = ForwardAddr_bytes.decode('ascii')  # 解析目的地址
                    MsgNum, = struct.unpack('!H',
                                            self.recvdata[(4 + byte + lenForwardAddr):(6 + byte + lenForwardAddr)])
                    lenDataMsg, = struct.unpack('!H',
                                                self.recvdata[(6 + byte + lenForwardAddr):(8 + byte + lenForwardAddr)])
                    DataMsg_bytes, = struct.unpack('!%ds' % (lenDataMsg), self.recvdata[(8 + byte + lenForwardAddr):(
                    8 + byte + lenForwardAddr + lenDataMsg)])
                    DataMsg = DataMsg_bytes.decode('ascii')  # 解析数据体
                    print("设备%s收到平台下发数据：%s（数据编号：%d）" % (ForwardAddr, DataMsg, MsgNum))
                    queuedata = DataMsg
                    queue.put(queuedata)
            else:
                pass  # 其余消息类型本项目不使用，暂不解析

#将收到的命令分解,并让煎药机执行响应的命令
class getcommand(threading.Thread):
    def run(self):
        global command,yao,xj_time,tj_time,ej_time,hx_time
        global queue
        while True:
            if queue.qsize() > 0:
                time.sleep(30)
                for i in range(queue.qsize()):
                    command += queue.get()
                if re.search(r'zibu:1',command):
                    yao = "zibu"
                elif re.search(r'jiebiao:1',command):
                    yao = "jiebiao"
                else:
                    yao = "yiban"
                try:
                    xj_time = int(re.search(r'\d',re.search(r'xianjian:\d',command).group()).group())
                except Exception:
                    xj_time = 0
                try:
                    tj_time = int(re.search(r'\d',re.search(r'toujian:\d',command).group()).group())
                except Exception:
                    tj_time = 0
                try:
                    ej_time = int(re.search(r'\d',re.search(r'erjian:\d',command).group()).group())
                except Exception:
                    ej_time = 0
                try:
                    hx_time = int(re.search(r'\d',re.search(r'houxia:\d',command).group()).group())
                except Exception:
                    hx_time = 0
                command = ""
                if xj_time + tj_time + ej_time + hx_time == 0:
                    general = ("python general_decoction.py %s" % yao)
                    os.system(general)
                else:
                    special = ("python special_decoction.py %s %d %d %d %d"%(yao,xj_time,tj_time,ej_time,hx_time))
                    os.system(special)
            else:
                time.sleep(30)

# 向OneNET设备云发送温度数据
class uptemp(threading.Thread):
    def run(self):
        while True:
            temp = read_temp(1)
            data = {"temp": temp}
            serNum = random.randint(1, 500)
            jianyaoji.savedata(data, serNum)
            time.sleep(10)

# mutex = Lock()    #创建互斥锁
command = ''
queue = Queue()  # 创建队列
jianyaoji = client("智能煎药机")
jianyaoji.connect(ProductID, AuthInfo)
p1 = threading.Thread(target=jianyaoji.ping)
p2 = threading.Thread(target=jianyaoji.recvDataAnalysis)
p3 = getcommand()
p4 = uptemp()

p2.start()
p3.start()
p4.start()
p1.start()

p2.join()
p3.join()
p4.join()
p1.join()
