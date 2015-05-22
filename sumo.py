#
#  JumpingSumo Client Library
#
#   Copyright(C) 2015, Isao Hara, AIST
#   Release under the MIT License.
#

import sys
import os
import socket
import select
import time
import threading
import struct
import copy
import json
import datetime

#
# Raw Socket Adaptor
#
#   threading.Tread <--- SocketAdaptor
#
class SocketAdaptor(threading.Thread):
  def __init__(self, reader, name, host, port, typ=True):
    threading.Thread.__init__(self)
    self.reader = reader
    self.name = name
    self.host = host
    self.port = port
    self.socket = None
    self.service = []
    self.service_id = 0
    self.client_adaptor = True
    self.mainloop = False
    self.debug = False
    self.locl = threading.Lock()
    if typ :
     self.socktype = socket.SOCK_STREAM
    else:
     self.socktype = socket.SOCK_DGRAM
  #
  #
  #
  def setHost(self, name):
    self.host = name
    return 

  def setPort(self, port):
    self.port = port
    return 

  def setType(self, typ):
    self.socktype = typ
    return 

  def setClientMode(self):
    self.client_adaptor = True
    return 

  def setServerMode(self):
    self.client_adaptor = False
    return 
  #
  # Bind
  #
  def bind(self):
    try:
      self.socket = socket.socket(socket.AF_INET, self.socktype)
      self.socket.bind((self.host, self.port))

    except socket.error:
      print "Bind error"
      self.close()
      return 0
    except:
      print "Error in bind " , self.host, self.port
      self.close()
      return -1

    return 1

  #
  # Connect
  #
  def connect(self, async=True):
    if self.mainloop :
      return 1

    try:
      self.socket = socket.socket(socket.AF_INET, self.socktype)
      self.socket.connect((self.host, self.port))

    except socket.error:
      print "Connection error"
      self.close()
      return 0

    except:
      print "Error in connect " , self.host, self.port
      self.close()
      return -1

    if async :
      print "Start read thread ",self.name
      self.start()

    return 1

  #
  #  Wait for comming data...
  #
  def wait_for_read(self, timeout=0.1):
    try:
      rready, wready, xready = select.select([self.socket],[],[], timeout)

      if len(rready) :
#        print "Ready to read:",self.name
        return 1
      return 0
    except:
      print "Error in wait_for_read"
      self.terminate()
      return -1

  #
  # Receive
  #
  def receive_data(self, bufsize=8192, timeout=1.0):
    data = None
    try:
      if self.wait_for_read(timeout) == 1  :
        data = self.socket.recv(bufsize)     # buffer size = 1024 * 8
        if len(data) != 0:
          return data
        else:
          return  -1

    except socket.error:
      print "socket.error in receive_data"
      self.terminate()

    except:
      print "Error in receive_data"
      self.terminate()

    return data

  def recv_data(self, bufsize=1024, timeout=1.0):
    while True:
      data = self.receive_data(bufsize, timeout)

      if data is None or data == -1:
        self.reader.clearBuffer()
        return None

      else :
        self.reader.appendBuffer(data)
        if self.reader.bufsize >= bufsize :
          data1 = self.reader.read(bufsize, 1)
          self.reader.parser.setBuffer(data1)
          return data1
        else:
#          print  "Size %d, %d" % (self.reader.bufsize, bufsize )
          pass
      
    return None
    
  #
  #
  #
  def getParser(self):
    return self.reader.parser
  #
  #  Thread oprations...
  #
  def start(self):
    self.mainloop = True
    threading.Thread.start(self)

  def run(self):
    if self.client_adaptor: 
      self.message_receiver()
    else:
      self.accept_service_loop()

  #
  # Backgrount job (server side)
  #
  def accept_service(self, flag=True):
    try:
      conn, addr = self.socket.accept()
      self.service_id += 1
      name = self.name+":service:%d" % self.service_id
      reader = copy.copy(self.reader)
      newadaptor = SocketAdaptor(self.reader, name, addr[0], addr[1])
      newadaptor.socket = conn
      self.service.append(newadaptor)
      if flag :
        newadaptor.start()
      return newadaptor
    except:
      print "ERROR in accept_service"
      pass
    return None

  def wait_accept_service(self, timeout=5, runflag=True):
    print "Wait for accept %d sec.: %s(%s:%d)" % (timeout, self.name, self.host, self.port)
    self.socket.listen(1)
    res = self.wait_for_read(timeout) 
    if res == 1:
      return self.accept_service(runflag)
    else:
      pass 
    return None

  def accept_service_loop(self, lno=5, timeout=1.0):
    print "Wait for accept: %s(%s:%d)" % (self.name, self.host, self.port)
    self.socket.listen(lno)
    while self.mainloop:
      res = self.wait_for_read(timeout) 
      if res == 1:
        self.accept_service()
      elif res == -1:
        self.terminate()
      else:
        pass
    
    print "Terminate all service %s(%s:%d)" % (self.name, self.host, self.port)
    self.close_service()
    self.close()
    return 
  #
  #  Background job ( message receiver )
  #
  def message_receiver(self):
    while self.mainloop:
      data = self.receive_data() 

      if data  == -1:
        self.terminate()

      elif data :
        if self.reader:
          self.reader.parse(data)
        else:
          print data

      elif data is None :
        pass

      else :
        print "Umm...:",self.name
        print data

    print "Read thread terminated:",self.name

  #
  #  close socket
  #
  def close_service(self):
    for s in  self.service :
      s.terminate()

  def close(self):
    if self.socket :
      self.socket.close()
      self.socket = None
  #
  #  Stop background job
  #
  def terminate(self):
    self.mainloop = False
    self.close()
  #
  #  Send message
  #
  def send(self, msg):
    if not self.socket :
      print "Error: Not connected"
      return None
    try:
      self.socket.sendall(msg)
    except socket.error:
      print "Socket error in send"
      self.close()
    return True


#
#  SumoSockSender
#      SocketAdaptor <---- SumoSockSender
#
class SumoSender(SocketAdaptor):
  def __init__(self, owner, myip="localhost", port=0):
    if owner:
      SocketAdaptor.__init__(self, None, owner.name+"Out", myip, port, False) 
    else:
      SocketAdaptor.__init__(self, None, "DebugOut", myip, port, False) 
    self.parser = SumoMarshaller()
    self.move_seq = 1
    self.ioctl_seq = 1
    self.cmd_seq = 1

    self.mainloop = 0
    self.intval = 0.005
    self.mv_speed = 0
    self.mv_turn = 0

    self.move_counter = 0

    self.cmd_activate = False

  def mkcmd1(self, klass, func, param):
    self.parser.initCommand('\x02\x0b\x00\x0f\x00\x00\x00\x03')
    self.parser.marshal('bHI',klass, func, param)

    self.parser.setSeqId(self.cmd_seq )
    self.cmd_seq = (self.cmd_seq + 1 ) % 256

    return self.parser.getEncodedCommand()

  def posture(self, param):
# param = enum[standing, jumper, kicker]
    cmd = self.mkcmd1(0, 1,param)
#    print[cmd]
    self.cmd_activate = True
    self.send(cmd)
    self.cmd_activate = False

  def action(self, param):
# param = enum[stop, spin, tap, slowshake, metronome, oudulation, spinjump, spintoposture, spiral,slalom]
    cmd = self.mkcmd1(2, 4, param)
#    print[cmd]
    self.cmd_activate = True
    self.send(cmd)
    self.cmd_activate = False

  def jump(self, param):
# param = enum[long, high]
    cmd = self.mkcmd1(2, 3, param)
#    print[cmd]
    self.cmd_activate = True
    self.send(cmd)
    self.cmd_activate = False

  def move(self, sp, turn=0, counter=-1):
    self.mv_speed = sp
    self.mv_turn = turn
    self.move_counter = counter

  def move_cmd(self):
    if self.move_counter == 0 :
      self.mv_speed = 0 
      self.mv_turn  = 0

    self.parser.initCommand('\x02\x0a\x00\x0e\x00\x00\x00\x03\x00\x00\x00')
    if self.mv_speed == 0 and self.mv_turn == 0 :
      self.parser.marshal('bbb', 0, 0, 0)
    else:
      self.parser.marshal('bbb', 1, self.mv_speed, self.mv_turn)

    self.parser.setSeqId(self.move_seq )
    self.move_seq = (self.move_seq + 1 ) % 256

    return self.parser.getEncodedCommand()

  def date_sync(self):
    self.parser.initCommand('\x04\x0b\x00\x16\x00\x00\x00\x04\x01\x00')
    self.parser.marshal('S', datetime.date.today().isoformat())

    self.parser.setSeqId(self.ioctl_seq )
    self.ioctl_seq = (self.ioctl_seq + 1 ) % 256

    return self.parser.getEncodedCommand()

  def time_sync(self):
    self.parser.initCommand('\x04\x0b\x00\x16\x00\x00\x00\x04\x02\x00')
    now=datetime.datetime.now()
    self.parser.marshal('S', now.strftime('T%H%M%S000'))

    self.parser.setSeqId(self.ioctl_seq )
    self.ioctl_seq = (self.ioctl_seq + 1 ) % 256

    return self.parser.getEncodedCommand()

  def image_ack(self):
    self.parser.initCommand('\x03\x0d\x00\x19\x00\x00\x00\x01\x00')
    self.parser.appendCommand('\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff')

  def run(self):
    self.send(self.move_cmd())

    while self.mainloop:
      if self.move_counter > 0:
        self.move_counter -= 1
      if not self.cmd_activate and self.send(self.move_cmd()) is None:

        self.terminate()
      time.sleep(self.intval)
    print "Sender '%s' thread is terminated." % (self.name,)


  def stop(self):
    self.mainloop = False
    print "ControlSender stopped"

#
#  SumoSockReceiver
#      SocketAdaptor <---- SumoSockReceiver
#
class SumoReceiver(SocketAdaptor):
  def __init__(self, owner, host, port):
    if owner:
      SocketAdaptor.__init__(self, SumoCommReader(owner), owner.name+"In", host, port, False) 
    else:
      SocketAdaptor.__init__(self, SumoCommReader(owner), "DebugIn", host, port, False) 

  def bind(self):
    if SocketAdaptor.bind(self) != 1 : return -1
    self.port = self.socket.getsockname()[1]
    return self.port


#
#  Foundmental reader class for Jumping Communiction
#
class SumoReaderBase:
  def __init__(self, owner=None, parser=None):
    self.buffer = ""
    self.bufsize = 0
    self.current=0
    self.owner = owner
    if parser is None:
      self.parser = SumoMarshaller('')
    else:
      self.parser = parser
 
    self.dataHandler = None
    if owner is None:
      self.debug = True
    else:
      self.debug = False

  #
  #  parse received data, called by SocketAdaptor
  #
  def parse(self, data):
    if self.debug:
      print data
    self.appendBuffer( data )

  #
  #  Usually 'owner' is a controller
  #
  def setOwner(self, owner):
    self.owner = owner

  #
  #  Buffer
  #
  def setBuffer(self, buffer):
    if self.buffer : del self.buffer
    self.buffer=buffer
    self.bufsize = len(buffer)
    self.current=0

  def appendBuffer(self, buffer):
    self.buffer += buffer
    self.bufsize = len(self.buffer)

  def skipBuffer(self, n=4, flag=1):
    self.current += n
    if flag :
      self.buffer = self.buffer[self.current:]
      self.current = 0
    return 

  def clearBuffer(self, n=0):
    if n > 0 :
#      self.printPacket( self.buffer[:n] )
      self.buffer = self.buffer[n:]
      self.current = 0
    else:
      if self.buffer : del self.buffer
      self.buffer = ""
      self.current = 0

  def checkBuffer(self):
    try:
      if len(self.buffer) > self.current :
        res = self.parser.checkMsgFormat(self.buffer, self.current)
        if res > 0:
          return res

        self.buffer = self.buffer[self.current:]
        self.current = 0
    except:
      print "ERR in checkBuffer"
      self.printPacket(self.buffer)
      self.buffer=""
      pass

    return 0
     
  #
  #  extract data from self.buffer 
  #
  def read(self, nBytes, delFlag=1):
    start = self.current
    end = start + nBytes

    if self.bufsize < end :
      end = self.bufsize

    data = self.buffer[start:end]
    self.current = end

    if  delFlag :
      self.buffer =  self.buffer[end:]
      self.current =  0
    return data

  #
  # print buffer (for debug)
  #
  def printPacket(self, data):
    if self.parser:
      self.parser.printPacket(data)
#
#
#
class SumoCommReader(SumoReaderBase):
  def __init__(self, owner=None, parser=None):
    SumoReaderBase.__init__(self, owner, parser)
  
  def parse(self, data):
    SumoReaderBase.parse(self, data)
    self.process()
    return

  def process(self):
    size = self.checkBuffer()
    if size > 0:
      data = self.read(size)
      self.printPacket(data)
      
    return

#
# Marshal/Unmarshal command packet for JumpingSumo
#
class SumoMarshaller:
  def __init__(self, buffer=''):
    self.buffer=buffer
    self.bufsize = len(buffer)

    self.offset=0

    self.header_size = self.calcsize('BBBHH')
    self.encbuf=None
    self.encpos=0

  #
  #  for buffer
  #
  def setBuffer(self, buffer):
    if self.buffer : del self.buffer
    self.buffer=buffer
    self.bufsize=len(buffer)
    self.offset=0

  def clearBuffer(self):
    self.setBuffer("")

  def appendBuffer(self, buffer):
    self.buffer += buffer
    self.bufsize = len(self.buffer)

  #
  #  check message format...  
  #
  def checkMsgFormat(self, buffer, offset=0):
    bufsize = len(buffer)

    if bufsize - offset >= self.header_size:
      self.buffer=buffer
      self.offset=offset
      (cmd, func, seq, size, fid) = self.unmarshal('bbbHH')

      if cmd in (0x01, 0x02, 0x03, 0x04):
        if size <= bufsize - offset:
          return size
        else:
          print "Short Packet %d/%d" % (bufsize, size)
          return 0

      else:
        print "Error in checkMsgFormat"
        return -1

    return 0

  #
  # extract message from buffer
  #
  def getMessage(self, buffer=None, offset=0):
    if buffer: self.buffer = buffer
    res =  self.checkMsgFormat(self.buffer, offset)

    if res > 0:
      start = offset 
      end =  offset + res
      cmd = self.buffer[start:end]
      self.buffer =  self.buffer[end:]
      self.offset =  0
      return cmd

    elif res == 0:
      return ''

    else:
      self.skipBuffer()
      return None

  #
  #  skip buffer, but not implemented....
  #
  def skipBuffer(self):
      print "call skipBuffer"
      return 
  #
  #  print buffer for debug
  #
  def printPacket(self, data):
    for x in data:
      print "0x%02x" % ord(x), 
    print

  #
  #  dencoding data
  # 
  def unmarshalString(self, offset=-1):
    if offset < 0 : offset=self.offset
    try:
     endpos = self.buffer.index('\x00', offset)
     size = endpos - offset
     if(size > 0):
       (str_res,) =  struct.unpack_from('!%ds' % (size), self.buffer, offset)
       self.offset += size + 1
       return str_res 
     else:
       return ""
    except:
      print "Error in parseCommand"
      return None

  def unmarshalNum(self, fmt, offset=-1):
    if offset < 0 : offset=self.offset
    try:
     (res,) =  struct.unpack_from(fmt, self.buffer, offset)
     self.offset = offset + struct.calcsize(fmt)
     return res
    except:
      print "Error in unmarshalNum"
      return None
     
  def unmarshalUShort(self, offset=-1):
    return self.unmarshalNum('<H', offset)
     
  def unmarshalUInt(self, offset=-1):
    return self.unmarshalNum('<I', offset)
     
  def unmarshalDouble(self, offset=-1):
    return self.unmarshalNum('d', offset)
     
  def unmarshalBool(self, offset=-1):
    return self.unmarshalNum('B', offset)

  def unmarshalByte(self, offset=-1):
    return self.unmarshalNum('b', offset)

  def unmarshalChar(self, offset=-1):
    return self.unmarshalNum('c', offset)

  def unmarshal(self, fmt):
    res=[]
    for x in fmt:
      if x in ('i', 'h', 'I', 'H'):
        res.append(self.unmarshalNum('<'+x))
      elif x in ('d', 'B', 'c', 'b'):
        res.append(self.unmarshalNum(x))
      elif x == 'S':
        res.append(self.unmarshalString())
    return res

  #  generate command
  #
  def createCommand(self):
    self.encbuf=bytearray()
    self.encpos=0 

  def initCommand(self, cmd):
    self.encbuf=bytearray(cmd)
    self.encpos=len(cmd) 

  def appendCommand(self, cmd):
    self.encbuf = self.encbuf + bytearray(cmd)
    self.encpos += len(cmd) 

  def setCommandSize(self):
    size = len(self.encbuf)
    struct.pack_into('<H', self.encbuf, 3, size)

  def setSeqId(self, sid):
    sid = sid % 256
    struct.pack_into('B', self.encbuf, 2, sid)

  def getEncodedCommand(self):
    self.setCommandSize()
    return str(self.encbuf)

  def getEncodedDataCommand(self):
    return str(self.encbuf)

  def clearEncodedCommand(self):
    if self.encbuf : del self.encbuf
    self.encbuf=None
    return
  #
  #  encoding data
  # 
  def marshalNumericData(self, fmt, s):
    enc_code = bytearray( struct.calcsize(fmt))
    struct.pack_into(fmt, enc_code, 0, s)
    self.encbuf = self.encbuf+enc_code
    self.encpos += struct.calcsize(fmt)

  def marshalChar(self, s):
    if type(s) == int:
      self.marshalNumericData('c', chr(s))
    else:
      self.marshalNumericData('c', s)

  def marshalUShort(self, s):
    self.marshalNumericData('>H', s)

  def marshalUInt(self, s):
    self.marshalNumericData('>I', s)

  def marshalDouble(self, d):
    self.marshalNumericData('>d', d)

  def marshalBool(self, d):
    if d :
      self.marshalNumericData('B', 1)
    else :
      self.marshalNumericData('B', 0)

  def marshalByte(self, d):
      self.marshalNumericData('b', d)

  def marshalString(self, str):
    size=len(str)
    enc_size = size+1
    enc_code = bytearray( size )

    if size > 0 :
      struct.pack_into('%ds' % (size,), enc_code, 0, str)

    self.encbuf = self.encbuf+enc_code+'\x00'
    self.encpos += enc_size

  def marshal(self, fmt, *data):
    pos = 0
    for x in fmt:
      if x in ('i', 'h', 'I', 'H', 'd'):
        self.marshalNumericData('<'+x, data[pos])
      elif x  == 'b':
        self.marshalByte(data[pos])
      elif x  == 'B':
        self.marshalBool(data[pos])
      elif x  == 'c':
        self.marshalChar(data[pos])
      elif x == 'S':
        self.marshalString(data[pos])
      elif x == 's':
        self.marshalString(data[pos], 0)
      pos += 1
    return 

  def calcsize(self, fmt):
    res = 0
    for x in fmt:
      if x in ('i', 'h', 'I', 'H', 'd', 'B'):
        res += struct.calcsize(x)
      else:
        print "Unsupported format:",x
    return res

  #
  #  print encoded data for debug
  #
  def printEncoded(self):
    count=0
    for x in self.encbuf:
      print "0x%02x" % x,
      if count % 8 == 7 : print
      count += 1
    print


#
#  Sample controller for Jumping Sumo
#
class SumoController:
  def __init__(self, name, host="192.168.2.1"):
    self.name=name
    self.host=host
    self.initport=44444
    self.recvport=0
    self.sendport=54321
    self.config={}

    myip = getipaddr(host, 0xffffff00)
    self.init_sock = SocketAdaptor(None, name, host, self.initport) 
    self.receiver = SumoReceiver(self, myip, self.recvport) 
    self.sender = SumoSender(self, host, self.sendport) 

  def connect(self):
    if self.receiver.bind() < 0 : return -1
    self.recvport = self.receiver.port
    if self.init_sock.connect(False) != 1 : return -1

    init_msg={}
    init_msg["controller_name"] = self.name
    init_msg["controller_type"] = "Python"
    init_msg["d2c_port"] = self.recvport

    self.init_sock.send(json.dumps(init_msg))
    res = self.init_sock.receive_data()

    if res and res != -1: 
      self.config = json.loads(res[:len(res)-1])
      self.sendport = self.config["c2d_port"]
      self.sender.setPort(self.sendport) 
      self.init_sock.terminate()
      self.sender.connect(False) 
    else:
      print "Fail to connect"
      self.init_sock.terminate()
      return

    self.receiver.start()
    self.sender.send(self.sender.date_sync())
    self.sender.send(self.sender.time_sync())
    self.sender.start()
    return

  def move(self, sp, turn=0, counter=-1):
    self.sender.move(sp, turn, counter)

  def posture(self, param):
    self.sender.posture(param)

  def jump(self, param):
    self.sender.jump(param)

  def action(self, param):
    self.sender.action(param)

  def stop(self):
    self.sender.move(0, 0)

  def terminate(self):
    self.receiver.terminate()
    self.sender.terminate()

############################################################################
# Global Functions...
#
def ip2hex(ipstr):
  ipar=ipstr.split('.')
  return int(ipar[0]) << 48 |int(ipar[1]) << 32 | int(ipar[2]) << 16 |int(ipar[3])

def ipcomp(ip1, ip2, msk=0xffffff00):
  iph1 = ip2hex(ip1) & msk
  iph2 = ip2hex(ip2) & msk
  return (iph1 == iph2)

def getipaddr(ip, msk=0xffffff00):
  ips = socket.gethostbyname_ex(socket.gethostname())[2]
  for x in ips:
    if ipcomp(x, ip, msk) :
      return x
  return socket.gethostbyname(socket.gethostname())

