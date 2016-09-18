#coding=utf-8
import os
import subprocess

from django.shortcuts import render,render_to_response
from django import forms

from pyltp import Segmentor, Postagger, Parser, NamedEntityRecognizer, SementicRoleLabeller

import time

from . import geoProcessor


# Create your views here.

class LTP_Processor():
    def __init__(self):
        self.parser = Parser()
        self.parser.load("C:\Python27\pyltp-master\ltp_data\parser.model")
        self.recognizer = NamedEntityRecognizer()
        self.recognizer.load("C:\Python27\pyltp-master\ltp_data\\ner.model")
        self.labeller = SementicRoleLabeller()
        self.labeller.load("C:\Python27\pyltp-master\ltp_data\srl")
    
    def srl(self,s):
        if s.strip()=="":
            return ""
        else:
            self.segmentor = Segmentor()
            self.segmentor.load("C:\Python27\pyltp-master\ltp_data\cws.model")
            self.postagger = Postagger()
            self.postagger.load("C:\Python27\pyltp-master\ltp_data\pos.model")

            words=self.segmentor.segment(s.strip())
            postags=self.postagger.postag(words)
            
            return self.srlWithWordsAndPostags(words,postags)

    def srlWithWordsAndPostags(self,words,postags):
        if len(words)!=len(postags):
            return "（错误：不匹配的分词和词性标注）"
        if len(words)==0:
            return ""
        arcs = self.parser.parse(words, postags)
        ner=self.recognizer.recognize(words,postags)
        roles = self.labeller.label(words, postags, ner, arcs)
        index=0
        '''
        for w in words:
            srlres+=str(index)+"/"+w+" "
            index+=1
        srlres+="<br>"
        '''
        srlres=""
        for role in roles:
            srlres+=str(role.index)
            srlres+=" ".join(["%s:(%d,%d)" % (arg.name, arg.range.start, arg.range.end) for arg in role.arguments])
            srlres+=" "
            
        return srlres

        
def berkeleyParser(infile,outfile):
    cmd="java -Xmx1024m -jar nlptools/BerkeleyParser/berkeleyParser-1.7.jar -gr nlptools/BerkeleyParser/chn_sm5.gr -useGoldPOS <"+infile+" >"+outfile
    print cmd
    #os.system(cmd)
    res=os.popen(cmd).readlines()
    print res
    for l in res:
            print l
        

def SentenceAnalyze(request):
    ltp=None
    if request.method=='POST':   #button for 'analyze'
        sentence=None
        print request.POST.get('sentence',"")
        if request.POST.get('sentence',"")!="":
            sentence=request.POST.get('sentence',"")
           
            analyze_res={}
            analyze_res['sentence']=sentence
            
            #使用组内为地理试题定制的工具
            geo=geoProcessor.geo_Processor()
            output_sentences=geo.process([sentence],1) 
            geo_res=output_sentences[0]

            #分词
            analyze_res['segres']=geo.get_seg_res(geo_res)
            
            #词性标注
            analyze_res['posres']=geo.get_pos_res(geo_res)
            
            #时间词
            analyze_res['timeres']=geo.get_entityTerm_res(geo_res,"time")
            
            #地点词
            analyze_res['locres']=geo.get_entityTerm_res(geo_res,"loc")

            #数量词
            analyze_res['quantres']=geo.get_entityTerm_res(geo_res,"num")

            #术语
            analyze_res['termres']=geo.get_entityTerm_res(geo_res,"term")

            
            #BParser
            
            print "BerkeleyParsing..."
            timestamp=time.time()
            timestamp=str(timestamp).replace(".","")
            
            infilename="SingleSentenceFiles/"+timestamp+".BerkeleyParser.in"            
            tmpfile=open(infilename,"w")

            input_sentences_goldseg=[[w.split("_")[0] for w in analyze_res['segres'].decode("utf-8").split()]]
            input_sentences_goldpos=[[w.split("_")[0] for w in analyze_res['posres'].decode("utf-8").split()]]

            for seg,pos in zip(input_sentences_goldseg,input_sentences_goldpos):
                for s,p in zip(seg,pos):
                    if p=="time":
                        p="NT"
                    elif p=="loc":
                        p="NR"
                    elif p=="term":
                        p="NN"
                    elif p=="num":
                        p="CD"
                    tmpfile.write(s.encode("gbk")+"\t"+p.encode("gbk")+"\n")
                tmpfile.write("\n")
            tmpfile.close()

            outfilename="SingleSentenceFiles/"+timestamp+".BerkeleyParser.out"
            
            berkeleyParser(infilename,outfilename)
            
            tmpoutfile=open(outfilename,"r")
            for line in tmpoutfile.readlines():    #only one sentence here
                analyze_res['bpres']=line.decode("gbk")
                print line
                break
            tmpoutfile.close()

            #删除相关文件
            os.remove(infilename)
            os.remove(outfilename)

            
            #语义角色标注
            '''
            if ltp==None:
                print "load ltp models..."
                ltp=LTP_Processor()
            print "semantic role labeling..."
            srlres=ltp.srl(sentence.encode('utf-8'))
            analyze_res['srlres']=srlres
            '''
            
            #模板填槽
            
            return render_to_response("SingleSentenceAnalyze.html",analyze_res)
        else:
            return render_to_response("SingleSentenceAnalyze.html",{'sentence':"请输入待分析的句子！"})

    return render_to_response("SingleSentenceAnalyze.html",{})


      
