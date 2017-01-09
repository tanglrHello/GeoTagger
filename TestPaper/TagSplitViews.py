#coding=utf-8
from django.shortcuts import render,render_to_response
from django.http import HttpResponse,HttpResponseRedirect

import pymongo
import json
import traceback
import mongoConnection

# Create your views here.
def tagSplit(request):
    #显示数据库中的内容至网页
    if request.method=='GET':
        papername=request.GET.get("papername")
        combinedChoiceIndex=request.GET.get("combinedChoiceIndex")

        #连接数据库
        conn=mongoConnection.connect_mongodb()
        
        GeoPaperDB=conn['GeoPaper']
        choiceCollection=GeoPaperDB['ChoiceData']
        
        paperInfo=choiceCollection.find_one({'testpaperName':papername})
        if paperInfo['States']['seg']==True:
            return HttpResponse(u"<h1>本试卷已完成分词标注，不能再标注拆分</h1><br><a href='./TagEachField.html?papername="+papername+u"'>前往单项标注页面</a>")
        
        findFlag,result=checkAndFindChoiceInDB(papername,combinedChoiceIndex)
        if findFlag==False:    
            #从浏览试卷页面过来的超链接，自动定位到第一个需要拆分的句子上
            if combinedChoiceIndex=="0":
                allValidIndex=result[2]
                if len(allValidIndex)==0:
                    checkGlobalSplitTagState(papername);
                    return HttpResponse(u"<h1>本试卷没有需要拆分的试题</h1><br><a href='./TagEachField.html?papername="+papername+u"'>前往单项标注页面</a>")
                else:
                    return HttpResponseRedirect('./TagSplit?papername='+papername+"&combinedChoiceIndex="+allValidIndex[0])
            return HttpResponse(u"<h1>非法访问，该试卷没有这个选项文本或不需要拆分！</h1><br><a href='./BrowseByPaper.html'>返回试卷列表页面</a>")
        else:
            textInfo=result[0]
            questionIndex=result[1]
            lastIndex=result[2]
            nextIndex=result[3]
            allValidIndex=result[4]
            #将text拆成题面和选项，供前端显示
            textInfo['timian']=textInfo['text'].split("\t")[0]
            textInfo['xuanxiang']=textInfo['text'].split("\t")[1]
            
            #判断选项中是否有逗号，如果没有则不需要拆分
            '''
            if u"，" not in textInfo["xuanxiang"]:
                return HttpResponse(u"<h1>非法访问，这个选项文本不需要拆分！</h1><p>该选项内容（包括题面）为："+textInfo['text']+u"</p><br><a href='./BrowseByPaper.html'>返回试卷列表页面</a>")
            '''

            splitRes=None
            if "splitRes" in textInfo:
                splitRes=textInfo['splitRes']
            
            return render_to_response("TagSplit.html",
                                    {'textInfo':textInfo,
                                    'splitRes':json.dumps(splitRes),
                                    'questionIndex':questionIndex,
                                    'lastIndex':lastIndex,
                                    'nextIndex':nextIndex,
                                    'papername':papername,
                                    'allValidIndex':json.dumps(allValidIndex)})
    #向数据库提交标注信息
    elif request.method=='POST':
        papername=request.GET.get("papername")
        combinedChoiceIndex=request.GET.get("combinedChoiceIndex")
        
        print request.POST
        
        #获取是否拆分的radio按钮结果
        splitFlag=False
        if u"NotSplit" in request.POST.get(u"split"):
            splitFlag=False
        elif u"DoSplit" in request.POST.get(u"split"):
            splitFlag=True        
            
        #获取拆分结果
        splitRes=[]
        if splitFlag:
            for i in range(10):
                partres=request.POST.get("part"+str(i))
                if partres:
                    splitRes.append(partres)
                else:
                    break

        #获取可能存在的标注者信息
        username=None
        if "username_name" in request.POST:
            username=request.POST['username_name']

                    
        if "save_btn" in request.POST:
            if saveSplitInfoToDB(papername,combinedChoiceIndex,splitRes,splitFlag,username):
                checkGlobalSplitTagState(papername)
                return HttpResponseRedirect('./TagSplit?papername='+papername+"&combinedChoiceIndex="+combinedChoiceIndex)
            else:
                return HttpResponse("保存出错")
        elif "saveAndNext_btn" in request.POST:
            if saveSplitInfoToDB(papername,combinedChoiceIndex,splitRes,splitFlag,username):
                checkGlobalSplitTagState(papername)
                nextIndex=checkAndFindChoiceInDB(papername,combinedChoiceIndex)[1][3]
                return HttpResponseRedirect('./TagSplit?papername='+papername+"&combinedChoiceIndex="+nextIndex)
            else:
                return HttpResponse("保存出错")

#检查并更新整张试卷的splitinfo标注状态
def checkGlobalSplitTagState(papername):
    # 连接数据库
    conn = mongoConnection.connect_mongodb()
    GeoPaperDB=conn['GeoPaper']
    choiceCollection=GeoPaperDB['ChoiceData']
    
    paperInfo=choiceCollection.find_one({'testpaperName':papername})
    nowstate=paperInfo['States']['split']
    if nowstate==True:
        return True
    else:
        newstate=True
        for question in paperInfo['Questions']:
            for ctext in question['combinedTexts']:
                if ctext['splitinfo']=="null":
                    newstate=False
                    break
        #如果该试卷的splitinfo全部标注完，则更新试卷的States中的split状态
        if newstate==True:
            paperInfo['States']['split']=True
            choiceCollection.save(paperInfo)
            return True
        else:
            return False
            
                    
                
def saveSplitInfoToDB(papername,combinedChoiceIndex,splitRes,splitFlag,username):
    # 连接数据库
    conn = mongoConnection.connect_mongodb()
    GeoPaperDB=conn['GeoPaper']
    choiceCollection=GeoPaperDB['ChoiceData']
    
    try:
        paperInfo=choiceCollection.find_one({'testpaperName':papername})
        if paperInfo==None:
            return False

        if username!="":
            paperInfo['relativeUsernames']['split_tagger']=username

        for question in paperInfo['Questions']:
            #print question['QuestionIndex']
            newCombinedTexts=[]
            for ctext in question['combinedTexts']:
                if combinedChoiceIndex==ctext['combinedChoiceIndex']:
                    oritext=ctext['text'].split("\t")[1].split(u"，")
                    #不拆分
                    if splitFlag==False:
                        ctext['splitinfo']="n"
                        newCombinedTexts.append(ctext)
                    #拆分
                    else:
                        ctext['splitinfo']="y"
                        ctext['splitRes']=splitRes
                        
                        newCombinedTexts.append(ctext)
                        #生成新的组合文本
                        for index,(ori,sub) in enumerate(zip(oritext,splitRes)):
                            newctext={
                            'combinedChoiceIndex':ctext['combinedChoiceIndex']+"-"+str(index),
                            'number':ctext['number']+'-'+str(index),
                            'text':"",
                            'splitinfo':"",
                            'segres':[],
                            'posres':[],
                            'goldtimes':[],
                            'goldlocs':[],
                            'bpres':"",
                            'simplifiedTemplate':"",
                            'simplifiedTemplateTypes':[],
                            'simplifiedTemplateCueword':"",
                            'fullTemplate':"",
                            'fullTemplateTypes':[],
                            'fullTemplateCueword':[]}
                            newctext['text']=ctext["text"].split("\t")[0]+"\t"+sub
                            if ori==sub:
                                newctext['splitinfo']="ed-ori"
                            else:
                                newctext['splitinfo']="ed-mod"
                            newCombinedTexts.append(newctext)
                else:
                    #不保留之前的拆分结果
                    if ctext['combinedChoiceIndex'].split("-")[0]!=combinedChoiceIndex:
                        newCombinedTexts.append(ctext)
                            
            question['combinedTexts']=newCombinedTexts
        #print paperInfo
        choiceCollection.save(paperInfo)
    except Exception, e:
        print e
        print traceback.format_exc()
        return False
    return True
                            
    

        
def checkAndFindChoiceInDB(papername,combinedChoiceIndex):
    # 连接数据库
    conn = mongoConnection.connect_mongodb()
    
    GeoPaperDB=conn['GeoPaper']
    choiceCollection=GeoPaperDB['ChoiceData']
    
    paperInfo=choiceCollection.find_one({'testpaperName':papername})
    if paperInfo==None:
        return False
    
    res=[]
    lastIndex=None
    nextIndex=None
    
    findFlag=False
    nextFlag=False
    
    allValidIndex=[]
    
    for question in paperInfo['Questions']:
        for ctext in question['combinedTexts']:
            #print ctext['combinedChoiceIndex'],"a"
            #如果选项中不含u"，"则不需要拆分
            if u"，" not in ctext['text'].split("\t")[1]:
                continue
                
            #print ctext['text'],ctext['combinedChoiceIndex'],"b"
            allValidIndex.append(ctext['combinedChoiceIndex'])
            
            if findFlag==True and nextFlag==False:   #只有在nextFlag为False的时候才对nextIndex赋值
                nextIndex=ctext['combinedChoiceIndex']
                nextFlag=True
            if findFlag==True:
                continue
            if combinedChoiceIndex==ctext['combinedChoiceIndex']:
                res.append(ctext)
                res.append(question['QuestionIndex'])
                findFlag=True
            else:
                lastIndex=ctext['combinedChoiceIndex']

    res.append(lastIndex)
    res.append(nextIndex)
    res.append(allValidIndex)
    if findFlag:        
        return True,res
    else:
        #如果遍历后没有找到则返回False
        return False,res
    
    
    
    
    
    