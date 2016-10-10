#coding=utf-8
from django.shortcuts import render,render_to_response
import pymongo
import os,time
from django import forms
import traceback

class ChoiceFileForm(forms.Form):
    uploadUserName=forms.CharField(widget=forms.TextInput(attrs={'id': 'cf_username_id'}))
    ChoiceFile=forms.FileField(widget=forms.FileInput(attrs={'class':'file','data-allowed-file-extensions':'["txt"]'}))

class SubjectiveFileForm(forms.Form):
    uploadUserName=forms.CharField(widget=forms.TextInput(attrs={'id': 'sf_username_id'}))
    SubjectiveFile=forms.FileField(widget=forms.FileInput(attrs={'class':'file','data-allowed-file-extensions':'["txt"]'}))

# Create your views here.
def addTestPaper(request):
    if request.method=="POST":
        #取锁（批量分析时会上锁，对上传试卷互斥）
        while os.path.exists("static/mongo.lock"):
            continue

        #上锁
        f=open("static/mongo.lock","w")
        f.close()

        papertype=None
        fileform=None
        filename=None
        filepath=None
        content=None
        emptyFlag=False
        if request.FILES.has_key("ChoiceFile"):
            papertype="choice"
            fileform=ChoiceFileForm(request.POST,request.FILES)
            if fileform.is_valid():
                filename = fileform.cleaned_data['ChoiceFile'].name
            else:
                emptyFlag=True
            
            filepath="TestPaperData/ChoiceData/";
            content=fileform.cleaned_data['ChoiceFile'].read()
        elif request.FILES.has_key("SubjectiveFile"):
            papertype="subjective"
            fileform=SubjectiveFileForm(request.POST,request.FILES)
            if fileform.is_valid():
                filename = fileform.cleaned_data['SubjectiveFile'].name
            else:
                emptyFlag=True
            
            filepath="TestPaperData/SubjectiveData/";
            content=fileform.cleaned_data['SubjectiveFile'].read()

        messages = {}

        if emptyFlag:
            messages['error_message']=u"请选择一个内容非空的txt文件！"
            cf=ChoiceFileForm()
            sf=SubjectiveFileForm()
            return render_to_response("AddTestPaper.html",{'cf':cf,'sf':sf,"messages":messages,papertype:True})

        print "uploading a "+papertype+" file.."

        #检查是否有同名文件
        if checkFileIsNew(filename,messages,papertype):
            username=fileform.cleaned_data['uploadUserName']
            if save_file(filename,content,messages,papertype):
                #解析文件，并结构化存储进数据库
                result=False
                try:
                    result=parseFileAndSaveToDatabase(filename,username,papertype)
                except Exception, e:
                    print e
                    print traceback.format_exc()
                    result="some exceptions occured in parseFileAndSaveToDatabase"
                print "***"
                print result
                if len(result)==3:   #解析并保存成功
                    messages['success_message']=u"上传成功！"
                    if result[1] or result[2]:
                        messages['success_message']+=u"【warning：但是存在下方所述的试题重复现象】"
                    messages['interpaper_repeat_message']=result[1]    #试卷整体重复信息
                    messages['innerpaper_repeat_message']=result[2]    #试卷内部小题重复信息
                else:    #没有解析并保存成功
                    del messages['success_message']
                    messages['error_message']=u"上传失败！"+result
                    #删除保存的文件
                    os.remove(filepath+filename)
    
        #还锁
        os.remove("static/mongo.lock")


        cf=ChoiceFileForm()
        sf=SubjectiveFileForm()
        return render_to_response("AddTestPaper.html",{'cf':cf,'sf':sf,"messages":messages,papertype:True})
        
    else:
        cf=ChoiceFileForm()
        sf=SubjectiveFileForm()
        return render_to_response("AddTestPaper.html",{'cf':cf,'sf':sf})

#检查是否存在于上传的文件同名的文件，不存在返回True
def checkFileIsNew(filename,messages,filetype):
    path=""
    if filetype=="choice":
        path="TestPaperData/ChoiceData/"
    else:
        path="TestPaperData/SubjectiveData/"
        
    exist_files=os.listdir(path)
    #print [filename,filename.encode('utf-8')]
    
    if filename.encode("utf-8") in exist_files:
        messages['error_message']=filename+u' 已存在重名的文件，不可覆盖！如果想上传，需要先删除相应试卷'
        return False
    else:
        return True

def save_file(filename,fileContent,messages,filetype):
    path=""
    print filetype
    if filetype=="choice":
        path="TestPaperData/ChoiceData/"
    else:
        path="TestPaperData/SubjectiveData/"
        
    #将文件保存在server上
    try:
        targetFile=open(path+filename,"w")
        targetFile.write(fileContent)
        targetFile.close()
        messages['success_message']=filename+u' 保存文件成功'
        return True
    except:
        messages['error_message']=filename+u' 保存文件失败'
        return False
        

def parseFileAndSaveToDatabase(filename,username,papertype):
    if papertype=="choice":
        return parseChoiceFileAndSaveToDatabase(filename,username)
    elif papertype=="subjective":
        return parseSubjectiveFileAndSaveToDatabase(filename,username)

def parseChoiceFileAndSaveToDatabase(filename,username):
    #********part 1：解析文件************
    print "parseChoiceFileAndSaveToDatabase"
    print "TestPaperData/ChoiceData/"+filename
    try:
        choiceFile=open("TestPaperData/ChoiceData/"+filename,'r')
        
        documentForMongo={}
        documentForMongo['originalFileText']=[]
        documentForMongo['testpaperName']=filename[:-4]
        documentForMongo['uploadTime']=time.strftime('%Y-%m-%d %H:%M:%S')
        documentForMongo['uploadTimestamp']=time.time()
        documentForMongo['SharedTexts']=[]
        documentForMongo['Questions']=[]
        documentForMongo['relativeUsernames']={"uploader":username}
        documentForMongo['States']={
                    'split':False,
                    'seg':False,
                    'pos':False,
                    'time':False,
                    'loc':False,
                    'term':False,
                    'quant':False,
                    'bpres':False,
                    "simplifiedTemplate":False,
                    "simplifiedTemplateTypes":False,
                    'simplifiedTemplateCueword':False,
                    "fullTemplateCueword":False,
                    "fullTemplateTypes":False,
                    "fullTemplate":False,
                    }
        
        for index,line in enumerate(choiceFile.readlines()):
            if line.strip()=="":
                continue
            
            #print line.decode("utf-8")
            line=line.decode("utf-8").strip()
            documentForMongo['originalFileText'].append(line)
            
            content=line.split("\t")
            if len(content)!=2:
                print "+++",len(content),content
                return u"第"+str(index+1)+u"行有超过一个Tab或有多余的未知符号"
            if "-" not in content[0]:
                return u"第"+str(index+1)+u"行编号有误，不含'-'"
            if len(content[0].split("-"))!=2:
                return u"第"+str(index+1)+u"行编号有误，应该只有一个'-'符号"  

            if "".join(content[0].split())!=content[0]:
                return u"第"+str(index+1)+u"行编号内部含有空白符号"   
            if "".join(content[1].split())!=content[1]:
                return u"第"+str(index+1)+u"行文本内部含有空白符号"
            if "," in content[1]:
                return u"第"+str(index+1)+u"行文本内部含有英文逗号（必须使用中文逗号）"
                
            number=content[0]
            #背景型题面（2-）
            if number[-1]=="-":
                #print "beijing"
                if number[:-1].isdigit() and int(number[:-1])==len(documentForMongo['SharedTexts'])+1:
                    documentForMongo['SharedTexts'].append(content[1])
                else:
                    if not number[:-1].isdigit():
                        return u"第"+str(index+1)+u"行的背景型题面题号"+number[:-1]+"有误，不是数字"
                    elif not int(number[:-1])==len(documentForMongo['SharedTexts'])+1:
                        return u"第"+str(index+1)+u"行的背景型题面题号"+number[:-1]+"有误，题号与前面的不连续"
                
            #小题题面（2-3）
            elif (number.split('-')[1].encode("utf-8")).isdigit():     #unicode下的"①"等字符会被isdigit()函数判断为true
                print "xiaoti"
                #print number
                #print [number.split('-')[1],number.split('-')[1]]
                #print number.split('-')[1].isdigit()
                if int(number.split("-")[1])!=len(documentForMongo['Questions'])+1:
                    return u"缺少第"+str(len(documentForMongo['Questions']))+u"小题" 
                if number[0]!='-' and (not number.split('-')[0].isdigit()):
                    return u"第"+str(index+1)+u"行的小题题面中，背景型题号部分不是有效数字"
                if number[0]!='-' and int(number.split("-")[0])!=len(documentForMongo['SharedTexts']):
                    return u"第"+str(index)+u"行的背景型题面题号与最近的背景型题面题号不匹配"
                
                sharedTextIndex=number.split('-')[0]
                questionIndex=number.split('-')[1]
                if sharedTextIndex=="":
                    sharedTextIndex=-1
                
                documentForMongo['Questions'].append({
                                            'sharedTextIndex':int(sharedTextIndex),
                                            'QuestionIndex':int(questionIndex),
                                            'timian':content[1],
                                            'choices':[],
                                            'smallChoices':[],
                                            'combinedTexts':[]})
            #选项或小选项
            elif number.split('-')[0].isdigit():
                #print "xuanxiang"
                if int(number.split('-')[0])!=len(documentForMongo['Questions']):
                    return u"第"+str(index+1)+u"行的选项的小题编号有误"
                    
                #存储原始选项
                if number.split('-')[1] in 'ABCD':  #普通选项
                    documentForMongo['Questions'][-1]['choices'].append({"choiceIndex":number.split('-')[1],"choiceContent":content[1]})
                else:
                    documentForMongo['Questions'][-1]['smallChoices'].append({"choiceIndex":number.split('-')[1],"choiceContent":content[1]})
            else:
                return u"第"+str(index+1)+u"行编号格式有误："+number
            
        #生成题面+选项/小选项的文本
        print "generate combinedChoice"
        combinedChoiceIndex=0   #记录已存在的该试卷中全部的组合选项的最大编号
        for index,question in enumerate(documentForMongo['Questions']):
            #检查选项的个数
            if len(question['choices'])!=4:
                return u"第"+str(index+1)+u"小题的选项个数不是4个"
            
            #判断使用普通选项还是小选项与题面进行组合
            if len(question['smallChoices'])==0:   #没有小选项，则题面+大选项     
                combinedChoice=question['choices']
            else:
                combinedChoice=question['smallChoices']
            
            #对每个选项/小选项与题面进行组合
            for choice in combinedChoice:
                combinedChoiceIndex+=1
                singleText={
                        'combinedChoiceIndex':str(combinedChoiceIndex),
                        'number':"",
                        'text':"",
                        'splitinfo':"",
                        'segres':[],
                        'posres':[],
                        'goldtimes':[],
                        'goldlocs':[],
                        'goldterms':[],
                        "goldquants":[],
                        'bpres':"",
                        'simplifiedTemplate':"",
                        "simplifiedTemplateTypes":[],
                        'simplifiedTemplateCueword':[],
                        'fullTemplate':"",
                        "fullTemplateTypes":[],
                        'fullTemplateCueword':[]}
                singleText['number']=choice['choiceIndex']
                singleText['text']=question['timian']+'\t'+choice['choiceContent']
                if u"，" not in choice['choiceContent']:
                    singleText['splitinfo']="None"
                question['combinedTexts'].append(singleText)
        
    except Exception, e:
        print e
        print traceback.format_exc()
        return u"解析出现错误。请检查是否文件编码为【utf-8无BOM格式】。"
    finally:
        choiceFile.close()
        
    
    
    
    #print documentForMongo
    #********part 1：解析文件（end）************
    #********part 2：连接并存储至数据库************
    configFile=open("static/config.txt",'r')
    mongoIP=configFile.readline().split("\t")[1].strip()
    mongoPort=int(configFile.readline().split("\t")[1].strip())
    conn=pymongo.Connection(mongoIP,mongoPort)
    
    geopaperDB=conn['GeoPaper']
    choiceCollection=geopaperDB['ChoiceData']
    choiceCollection.insert(documentForMongo)

    #试卷整体查重
    repeat_lines=checkRepeatPaper("choice",filename)

    #试卷内部小题查重
    repeat_questions=checkRepeatQuestion("choice",filename)
    
    print "parseChoiceFileAndSaveToDatabase(end)"
    return True,repeat_lines,repeat_questions

def parseSubjectiveFileAndSaveToDatabase(filename,username):
    print "parseSubjectiveFileAndSaveToDatabase"
    try:
        subjectiveFile=open("TestPaperData/SubjectiveData/"+filename,'r')

        documentForMongo={}
        documentForMongo['originalFileText']=[]
        documentForMongo['testpaperName']=filename[:-4]
        documentForMongo['uploadTime']=time.strftime('%Y-%m-%d %H:%M:%S')
        documentForMongo['uploadTimestamp']=time.time()
        documentForMongo['Questions']=[]
        documentForMongo['relativeUsernames']={'uploader':username}
        documentForMongo['States']={
                    'seg':False,
                    'pos':False,
                    'time':False,
                    'loc':False,
                    'term':False,
                    'quant':False,
                    'bpres':False,
                    "simplifiedTemplate":False,
                    "simplifiedTemplateTypes":False,
                    'simplifiedTemplateCueword':False,
                    "fullTemplateCueword":False,
                    "fullTemplateTypes":False,
                    "fullTemplate":False
                    }

        
        smallQuestion={}
        question={}

        subQuestionIndex=0
        for index,line in enumerate(subjectiveFile.readlines()):
            if line.strip()=="":
                continue

            line=line.decode('utf-8').strip()
            documentForMongo['originalFileText'].append(line)

            content=line.split("\t")
            if len(content)!=2:
                return u"第"+str(index+1)+u"行有超过一个Tab或有多余的未知符号"
            if "-" not in content[0]:
                return u"第"+str(index+1)+u"行编号有误，不含'-'" 

            if "".join(content[0].split())!=content[0]:
                return u"第"+str(index+1)+u"行编号内部含有空白符号"   
            if "".join(content[1].split())!=content[1]:
                return u"第"+str(index+1)+u"行文本内部含有空白符号"  

            number=content[0]
            
            #大题题面
            current_question_index=None   #大题序号
            number_segs=number.split("-")
            if len(number_segs)==2 and number_segs[1]=="":
                if number_segs[0].isdigit==False:
                    return u"第"+str(index+1)+u"行的大题编号"+number_segs[0]+"不是数字" 

                if len(documentForMongo['Questions'])>0:
                    q=documentForMongo['Questions'][-1]
                    if q['number']>=int(number_segs[0]):
                        return u"第"+str(index+1)+u"行的大题编号小于等于前面出现的大题编号"

                #把上一大题的最后一小题存起来
                if smallQuestion!={}:
                    question['subQuestions'].append(smallQuestion)
                    smallQuestion={}
                #把上一大题存起来
                if question!={}:
                    documentForMongo['Questions'].append(question)


                question={}

                question['text']=content[1]
                print index,number_segs
                question['number']=int(number_segs[0])
                question['backgroudTexts']=[]
                question['subQuestions']=[] 
            
            #背景型题面
            if len(number_segs)==2 and number_segs[1]!="":
                if question=={}:
                    return u"第"+str(index+1)+u"行的背景型题面之前没有相应的大题"
                if number_segs[0].isdigit==False:
                    return u"第"+str(index+1)+u"行的大题编号"+number_segs[0]+u"不是数字" 
                if not number_segs[1].isdigit():
                    return u"第"+str(index+1)+u"行的背景型题面题号"+number_segs[1]+u"有误，不是数字"
                if int(number_segs[1])!=len(question['backgroudTexts'])+1:
                    return u"第"+str(index+1)+u"行的背景型题面编号"+number_segs[1]+u"与前面的不连续"
                question['backgroudTexts'].append(content[1])
            
            #小题题面
            if len(number_segs)==3:
                if question=={}:
                    return u"第"+str(index+1)+u"行的小题题面之前没有相应的大题"
                if number_segs[0].isdigit()==False:
                    return u"第"+str(index+1)+u"行的小题题面编号中大题编号部分不是数字"
                if int(number_segs[0])!=question['number']:
                    return u"第"+str(index+1)+u"行的小题题面编号与最近的小题题面编号不一致"
                for bt in number_segs[1].split("/"):   #可能有多个背景题面
                    if bt=="":
                        continue
                    if bt.isdigit()==False:
                        return u"第"+str(index+1)+u"行的背景型题面编号部分中存在非数字"
                    if int(bt)>len(question['backgroudTexts']):
                        return u"第"+str(index+1)+u"行的背景型题面编号在该题中从开头至此行中不存在"
                
                if number_segs[2].isdigit==False:
                    return u"第"+str(index+1)+u"行的小题编号不是数字"

                if len(question['subQuestions'])>0 and int(number_segs[2])<=question['subQuestions'][-1]['number']:
                    print number_segs[2],question['subQuestions'][-1]
                    return u"第"+str(index+1)+u"行的小题编号小于等于该大题中的上一个小题编号"

                #把上一个小题放入question中，并清空smallQuestion
                if smallQuestion!={}:
                    question['subQuestions'].append(smallQuestion)

                smallQuestion={}
                smallQuestion['backgroudTextIndexes']=number_segs[1]
                smallQuestion['number']=int(number_segs[2])
                smallQuestion['text']=content[1]
                subQuestionIndex+=1
                smallQuestion['subQuestionIndex']=str(subQuestionIndex)
                print subQuestionIndex

            #小题中嵌套的子题
            if len(number_segs)==4:
                if question=={}:
                    return u"第"+str(index+1)+u"行的子题编号没有对应的大题"
                if int(number_segs[0])!=question['number']:
                    return u"第"+str(index+1)+u"行的子题编号中的大题编号与最近的大题不相同"
                if number_segs[1]!=smallQuestion['backgroudTextIndexes']:
                    return u"第"+str(index+1)+u"行的子题编号与其所属的小题的背景型题面编号部分不相同"

                #把上一个小题放入question中，并清空smallQuestion
                if smallQuestion!={}:
                    question['subQuestions'].append(smallQuestion)

                for q in question['subQuestions'][::-1]:
                    #print question['subQuestions']
                    if "-" not in str(q['number']):
                        if str(q['number'])!=number_segs[2]:
                            return u"第"+str(index+1)+u"行的子题编号中的小题编号与最近的小题不相同"
                        break
                else:
                    return u"第"+str(index+1)+u"行的子题之前没有小题"

                if number_segs[3].isdigit()==False:
                    return u"第"+str(index+1)+u"行的子题编号不是数字"                

                smallQuestion={}
                smallQuestion['backgroudTextIndexes']=number_segs[1]
                smallQuestion['number']=number_segs[2]+'-'+number_segs[3]
                smallQuestion['text']=content[1]
                subQuestionIndex+=1
                smallQuestion['subQuestionIndex']=str(subQuestionIndex)

        #把最后一小题存起来
        question['subQuestions'].append(smallQuestion)

        #把最后一大题存起来
        documentForMongo['Questions'].append(question)

    except Exception,e:
        print e
        print traceback.format_exc()
        return u"解析出现错误。请检查是否文件编码为【utf-8无BOM格式】。"
    finally:
        subjectiveFile.close()

    #print documentForMongo
    #********part 1：解析文件（end）************
    #********part 2：连接并存储至数据库************
    configFile=open("static/config.txt",'r')
    mongoIP=configFile.readline().split("\t")[1].strip()
    mongoPort=int(configFile.readline().split("\t")[1].strip())
    conn=pymongo.Connection(mongoIP,mongoPort)
    
    geopaperDB=conn['GeoPaper']
    subjectiveCollection=geopaperDB['SubjectiveData']
    subjectiveCollection.insert(documentForMongo)

    #试卷整体查重
    repeat_lines=checkRepeatPaper("subjective",filename)

    #试卷内部小题查重
    repeat_questions=checkRepeatQuestion("subjective",filename)
    
    print "parseChoiceFileAndSaveToDatabase(end)"
    return True,repeat_lines,repeat_questions


#针对选择题，为查重函数提取结构化的试题列表，每个元素是一个列表，表示一个小题，有5个元素，对应题面和4个选项
def extractChoiceQuestionsForCkeckRepeat(filepath):
    f=open(filepath)

    question_list=[]
    question=[]

    for line in f.readlines():
        if line.strip()=="":
            continue
        line=line.strip()

        if line.split("\t")[0].split("-")[1].isdigit():
            question.append(line.split("\t")[1])
        elif line.split("\t")[0].split("-")[1]!="":
            question.append(line.split("\t")[1])

        if len(question)==5:
            question_list.append(question)
            question=[]
    f.close()

    return question_list

#针对主观题，为查重函数提取大题题面列表，每个元素是一个大题的题面内容
def extractSubjectiveQuestionsForCkeckRepeat(filepath):
    print filepath
    f=open(filepath)
    question_list=[]
    for line in f.readlines():
        if line.strip()=="":
            continue
        line=line.strip()

        number=line.split("\t")[0]
        text=line.split("\t")[1]
        if len(number.split("-"))==2 and number.split("-")[1]=="":
            question_list.append((number.split("-")[0],text))
    f.close()

    return question_list


#文件解析正常之后，才会调用本函数进行试卷整体查重
#返回一个重复列表，key为与被检查文件有相同行内容的文件名，value为一个二元组，对应（新试卷中的题号，旧试卷中的题号）
def checkRepeatPaper(papertype,newfile_name):
    repeat_list={}
    newfile_question_list=None

    if papertype=="choice":
        data_dir="TestPaperData/ChoiceData/"
        newfile_question_list=extractChoiceQuestionsForCkeckRepeat(data_dir+newfile_name)
    elif papertype=="subjective":
        data_dir="TestPaperData/SubjectiveData/"
        newfile_question_list=extractSubjectiveQuestionsForCkeckRepeat(data_dir+newfile_name)


    

    for oldfile_name in os.listdir(data_dir):
        try:
            if oldfile_name.decode('utf-8')==newfile_name.decode('utf-8'):
                continue
        except:
            try:
                if oldfile_name.decode('utf-8')==newfile_name:
                    continue
            except:
                try:
                    if oldfile_name==newfile_name.decode('utf-8'):
                        continue
                except:
                    try:
                        if oldfile_name==newfile_name:
                            continue
                    except Exception,e:
                        print e
                        print traceback.format_exc()


        oldfile_question_list=None
        if papertype=="choice":
            oldfile_question_list=extractChoiceQuestionsForCkeckRepeat(data_dir+oldfile_name)
        elif papertype=="subjective":
            oldfile_question_list=extractSubjectiveQuestionsForCkeckRepeat(data_dir+oldfile_name)
        
        repeat_pairs=[]
        for index1 in range(len(oldfile_question_list)):
            for index2 in range(len(newfile_question_list)):
                if papertype=="choice":
                    for c1,c2 in zip(oldfile_question_list[index1],newfile_question_list[index2]):
                        if c1!=c2:
                            break
                    else:
                        repeat_pairs.append((index1+1,index2+1))
                elif papertype=="subjective":
                    if oldfile_question_list[index1][1]==newfile_question_list[index2][1]:
                        repeat_pairs.append((oldfile_question_list[index1][0],newfile_question_list[index2][0]))

        if len(repeat_pairs)!=0:
            repeat_list[oldfile_name.decode("utf-8")]=repeat_pairs
    print repeat_list,"+++"
    return repeat_list


#文件解析正常之后，才会调用本函数进行试卷内部查重
#返回一个重复列表，每个元素是一个二元组，为重复的一对试题序号（只检查小题粒度,只检查题面和ABCD选项，不检查小选项）
def checkRepeatQuestion(papertype,filename):
    repeat_list=[]
    question_list=None
    if papertype=="choice":
        data_dir="TestPaperData/ChoiceData/"
        question_list=extractChoiceQuestionsForCkeckRepeat(data_dir+filename)
    elif papertype=="subjective":
        data_dir="TestPaperData/SubjectiveData/"
        question_list=extractSubjectiveQuestionsForCkeckRepeat(data_dir+filename)
        

    #题间查重
    for index1 in range(len(question_list)):
        for index2 in range(index1+1,len(question_list)):
            if papertype=="choice":
                q1=question_list[index1]
                q2=question_list[index2]

                for c1,c2 in zip(q1,q2):
                    if c1!=c2:
                        break
                else:
                    repeat_list.append((index1+1,index2+1))
            elif papertype=="subjective":
                if question_list[index1][1]==question_list[index2][1]:
                    repeat_list.append((question_list[index1][0],question_list[index2][0]))
    print repeat_list,"---"
    return repeat_list