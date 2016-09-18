#coding=utf-8
from django.shortcuts import render,render_to_response
from django.http import HttpResponse,HttpResponseRedirect

import pymongo
import time,json
import traceback

import os

# Create your views here.
def tagConpparse(request):
    #连接数据库
    configFile=open("static/config.txt",'r')
    mongoIP=configFile.readline().split("\t")[1].strip()
    mongoPort=int(configFile.readline().split("\t")[1].strip())
    conn=pymongo.Connection(mongoIP,mongoPort)

    GeopaperDB=conn['GeoPaper']

    papername=request.GET['papername']
    papertype=request.GET['papertype']
    
    dataCollection=None
    globalIndexFieldName=None
    globalIndex=None
    textFieldName=None
    if papertype=="choice":
        dataCollection=GeopaperDB['ChoiceData']
        globalIndexFieldName="combinedChoiceIndex"
        globalIndex=request.GET['combinedChoiceIndex']
        textFieldName="combinedTexts"
    elif papertype=="subjective":
        dataCollection=GeopaperDB['SubjectiveData']
        globalIndexFieldName="subQuestionIndex"
        globalIndex=request.GET['subQuestionIndex']
        textFieldName="subQuestions"


    paperInfo=dataCollection.find_one({'testpaperName':papername})  
    if not paperInfo:
        return HttpResponse("没有这份试卷")

    #必须是时间地点手动标注完了才来标注时间地点(这里使用粗粒度的版本)
    if paperInfo['States']['pos']!=True or paperInfo['States']['seg']!=True: 
        return HttpResponse("请先完成对该试卷的分词和词性标注")
    
    result=checkAndFindTextInfoInDB(papername,papertype,globalIndex)


    if result==False:
        return HttpResponse("<h1>非法访问，该试卷没有这个选项文本")

    textInfo=result[0]
    questionIndex=result[1]
    lastIndex=result[2]
    nextIndex=result[3]
    allValidIndex=result[4]

    tagtype="null"
    
    if papertype=="choice":
        #将text拆成题面和选项，供前端显示
        textInfo['timian']=textInfo['text'].split("\t")[0]
        textInfo['xuanxiang']=textInfo['text'].split("\t")[1]
        textInfo['combinedTextWithoutTab']=textInfo['text'].replace("\t","")
    
    textInfo['segpos']=" ".join([s+"_"+p for s,p in zip(textInfo['segres'],textInfo['posres'])])

    if request.method=='GET':  
        if 'bpres' not in textInfo:   #主观题没有标注结果的时候
            textInfo['conpparse']=textInfo['text']
            tagtype="暂无标注"
        elif textInfo['bpres'].strip()!="":
            textInfo['conpparse']=textInfo['bpres']
            tagtype="人工标注结果"
        elif "auto_bpres" in textInfo and textInfo['auto_bpres']!="":
            textInfo['conpparse']=textInfo['auto_bpres']
            tagtype="自动标注结果"
        else:                        #选择题没有标注结果的时候
            textInfo['conpparse']=textInfo['combinedTextWithoutTab']
            tagtype="暂无标注"

        #textInfo['conpparse']='( (IP (NP (LCP (NP (NN 图)) (LC 中)) (NP (NR ②) (NN 山脉))) (VP (VC 是) (NP (DNP (NP (NN 我国) (NN 湿润区) (CC 和) (NN 半湿润区)) (DEG 的)) (NP (NN 分界线))))) )'
        
        return render_to_response("TagConpparse.html",
                            {"restype":tagtype,
                            'textInfoJson':json.dumps(textInfo),
                            'textInfo':textInfo,
                            'questionIndex':questionIndex,
                            'lastIndex':lastIndex,
                            'thisIndex':globalIndex,
                            'nextIndex':nextIndex,
                            'papertype':papertype,
                            'papername':papername,
                            'allValidIndex':json.dumps(allValidIndex)})

    elif request.method=="POST" and "generateBPres" in request.POST:   #自动生成整张试卷所有试题文本的成分分析结果
        input_sentences_goldseg=[]
        input_sentences_goldpos=[]        

        for question in paperInfo['Questions']:
            for ctext in question[textFieldName]:
                input_sentences_goldseg.append(ctext['segres'])
                input_sentences_goldpos.append(ctext['posres'])

        #自动parsing
        print "BerkeleyParsing..."
        timestamp=time.time()
        timestamp=str(timestamp).replace(".","")
        
        infilename="SingleSentenceFiles/"+timestamp+".BerkeleyParser.in"            
        tmpfile=open(infilename,"w")
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

                tmpfile.write(s.encode("utf-8")+"\t"+p.encode("utf-8")+"\n")
            tmpfile.write("\n")
        tmpfile.close()

        outfilename="SingleSentenceFiles/"+timestamp+".BerkeleyParser.out"
        
        cmd="java -Xmx1024m -jar nlptools/BerkeleyParser/berkeleyParser-1.7.jar -gr nlptools/BerkeleyParser/chn_sm5.gr -useGoldPOS <"+infilename+" >"+outfilename
        print cmd
        #os.system(cmd)
        res=os.popen(cmd).readlines()
        print res
        for l in res:
            print l

        #将自动分析的结果写回数据库
        paperInfo=dataCollection.find_one({'testpaperName':papername})  
        outfile=open(outfilename,"r")
        for question in paperInfo['Questions']:
            for ctext in question[textFieldName]:            
                ctext["auto_bpres"]=outfile.readline().decode("utf-8").strip()
                if 'auto_conpparse_valid' in ctext:
                    del ctext['auto_conpparse_valid']
                if globalIndex==ctext[globalIndexFieldName]:
                    textInfo['conpparse']=ctext['auto_bpres']
                    tagtype="自动标注结果"
        outfile.close()

        #删除相关文件
        os.remove(infilename)
        os.remove(outfilename)

        paperInfo['States']['auto_bpres']=True

        dataCollection.save(paperInfo)

        return render_to_response("TagConpparse.html",
                                {"restype":tagtype,
                                'textInfoJson':json.dumps(textInfo),
                                'textInfo':textInfo,
                                'questionIndex':questionIndex,
                                'lastIndex':lastIndex,
                                'thisIndex':globalIndex,
                                'nextIndex':nextIndex,
                                'papertype':papertype,
                                'papername':papername,
                                'allValidIndex':json.dumps(allValidIndex)})


    elif request.method=='POST':
        tagInfo={}
        tagInfo['bpres']=request.POST.get("conpparse_input_new_name")
        print tagInfo
        username=request.POST.get("username_name")
        if "save_btn" in request.POST:
            if saveTagInfoToDB(papername,papertype,globalIndex,tagInfo,username):
                checkGlobalTagState(papername,papertype)
                return HttpResponseRedirect('./TagConpparse?papername='+papername+"&papertype="+papertype+"&"+globalIndexFieldName+"="+globalIndex)
            else:
                return HttpResponse("保存出错")
        elif "saveAndNext_btn" in request.POST:
            if saveTagInfoToDB(papername,papertype,globalIndex,tagInfo,username):
                checkGlobalTagState(papername,papertype)
                nextIndex=checkAndFindTextInfoInDB(papername,papertype,globalIndex)[3]
                return HttpResponseRedirect('./TagConpparse?papername='+papername+"&papertype="+papertype+"&"+globalIndexFieldName+"="+nextIndex)
            else:
                return HttpResponse("保存出错")
    


def checkAndFindTextInfoInDB(papername,papertype,globalIndex):
    #连接数据库
    configFile=open("static/config.txt",'r')
    mongoIP=configFile.readline().split("\t")[1].strip()
    mongoPort=int(configFile.readline().split("\t")[1].strip())
    conn=pymongo.Connection(mongoIP,mongoPort)
    
    GeoPaperDB=conn['GeoPaper']
    
    dataCollection=None
    globalIndexFieldName=None
    textFieldName=None
    if papertype=="choice":
        dataCollection=GeoPaperDB['ChoiceData']
        globalIndexFieldName="combinedChoiceIndex"
        textFieldName="combinedTexts"
    elif papertype=="subjective":
        dataCollection=GeoPaperDB['SubjectiveData']
        globalIndexFieldName="subQuestionIndex"
        textFieldName="subQuestions"

    paperInfo=dataCollection.find_one({'testpaperName':papername})
    if paperInfo==None:
        return False
    
    res=[]
    lastIndex=None
    nextIndex=None
    
    findFlag=False
    nextFlag=False
    
    allValidIndex=[]

    for question in paperInfo['Questions']:
        for ctext in question[textFieldName]:
            allValidIndex.append(ctext[globalIndexFieldName])
            if findFlag==True and nextFlag==False:   #只有在nextFlag为False的时候才对nextIndex赋值
                nextIndex=ctext[globalIndexFieldName]
                nextFlag=True
            if findFlag==True:
                continue
            if globalIndex==ctext[globalIndexFieldName]:        
                res.append(ctext)
                if papertype=="choice":
                    res.append(question['QuestionIndex'])
                elif papertype=="subjective":
                    res.append(question['number'])
                findFlag=True
            else:
                lastIndex=ctext[globalIndexFieldName]
            
    if findFlag:
        res.append(lastIndex)
        res.append(nextIndex)
        res.append(allValidIndex)
        return res
    else:
        #如果遍历后没有找到则返回False
        return False

def saveTagInfoToDB(papername,papertype,globalIndex,tagInfo,username):
    #连接数据库
    configFile=open("static/config.txt",'r')
    mongoIP=configFile.readline().split("\t")[1].strip()
    mongoPort=int(configFile.readline().split("\t")[1].strip())
    conn=pymongo.Connection(mongoIP,mongoPort)
    GeoPaperDB=conn['GeoPaper']
    
    dataCollection=None
    globalIndexFieldName=None
    textFieldName=None
    if papertype=="choice":
        dataCollection=GeoPaperDB['ChoiceData']
        globalIndexFieldName="combinedChoiceIndex"
        textFieldName="combinedTexts"
    elif papertype=="subjective":
        dataCollection=GeoPaperDB['SubjectiveData']
        globalIndexFieldName="subQuestionIndex"
        textFieldName="subQuestions"
    
    try:
        paperInfo=dataCollection.find_one({'testpaperName':papername})
        if paperInfo==None:
            return False
        for question in paperInfo['Questions']:
            for ctext in question[textFieldName]:
                if globalIndex==ctext[globalIndexFieldName]:
                    ctext['conpparse_tagger']=username
                    ctext['bpres']=tagInfo['bpres']
                    if 'conpparse_valid' in ctext:
                        del ctext['conpparse_valid']
                        
                    print "save bpres here...."

        dataCollection.save(paperInfo)
    except Exception, e:
        print e
        print traceback.format_exc()
        return False
    return True

def checkGlobalTagState(papername,papertype):
    #连接数据库
    configFile=open("static/config.txt",'r')
    mongoIP=configFile.readline().split("\t")[1].strip()
    mongoPort=int(configFile.readline().split("\t")[1].strip())
    conn=pymongo.Connection(mongoIP,mongoPort)
    GeoPaperDB=conn['GeoPaper']
    choiceCollection=GeoPaperDB['ChoiceData']
    
    dataCollection=None
    globalIndexFieldName=None
    textFieldName=None
    if papertype=="choice":
        dataCollection=GeoPaperDB['ChoiceData']
        globalIndexFieldName="combinedChoiceIndex"
        textFieldName="combinedTexts"
    elif papertype=="subjective":
        dataCollection=GeoPaperDB['SubjectiveData']
        globalIndexFieldName="subQuestionIndex"
        textFieldName="subQuestions"

    paperInfo=dataCollection.find_one({'testpaperName':papername})

    conp_state=True

    taggers={}
    for question in paperInfo['Questions']:
        for ctext in question[textFieldName]:
            if 'bpres' not in ctext or ctext['bpres']=="" or 'conpparse_valid' in ctext and ctext['conpparse_valid']==False:
                conp_state=False
            else:
                if ctext['conpparse_tagger'] not in taggers:
                    taggers[ctext['conpparse_tagger']]=1
                else:
                    taggers[ctext['conpparse_tagger']]+=1

    paperInfo['relativeUsernames']['conpparse_tagger']=list(taggers)
        
    paperInfo['States']['bpres']=conp_state

    dataCollection.save(paperInfo)

    return paperInfo['States']