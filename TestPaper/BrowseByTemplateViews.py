#coding=utf-8
from django.shortcuts import render,render_to_response
from django.http import HttpResponse
import mongoConnection
import json
import time
import os,shutil
import zipfile
import StringIO

from . import getConfig

# Create your views here.
def browseByTemplate(request):
    # 连接数据库
    conn = mongoConnection.connect_mongodb()

    GeopaperDB=conn['GeoPaper']

    papertype=None
    if 'papertype' not in request.GET:
        papertype="choice"
    else:
        papertype=request.GET['papertype']

    dataCollection=None
    globalIndexFieldName=None
    questionIndexFieldName=None
    textFieldName=None
    if papertype=="choice":
        dataCollection=GeopaperDB['ChoiceData']
        textFieldName="combinedTexts"
        questionIndexFieldName="QuestionIndex"
        globalIndexFieldName="combinedChoiceIndex"
        # 获取模板配置信息
        template_Info = getConfig.getNewTemplateConfig(papertype)
    elif papertype=="subjective":
        dataCollection=GeopaperDB['SubjectiveData']
        textFieldName="subQuestions"
        questionIndexFieldName="number"
        globalIndexFieldName="subQuestionIndex"
        # 获取模板配置信息
        template_Info = getConfig.getTemplateConfig(papertype)
    else:
        return HttpResponse("<h1>非法访问，没有提供试卷类型！</h1><br><a href='./BrowseByPaper.html'>返回试卷列表页面</a>")
    
    #获取标注字段配置信息
    tagFields_Info = getConfig.getTagFieldConfig(papertype)
    sortedTagFieldsForTable = tagFields_Info[:]
    sortedTagFieldsForTable.sort(key=lambda x: x[-1])
    
    if request.method == 'POST' and "template" in request.POST:   #查询某种模板的所有句子的请求
        papers = dataCollection.find()

        print request.POST
        templateToExtract = request.POST['template']  # such as 'yyRadio'

        # tname is the chinese representation of this template, while templateToExtract is english
        for t in template_Info:
            if templateToExtract == t[1] + "Radio":
                tname = t[0].decode('utf-8')
                break
        else:
            print "unknown templateType:"+templateToExtract
            tname = None
        
        #在数据库中查找数据
        queryRes = []
        for paper in papers:
            for question in paper['Questions']:
                for ctext in question[textFieldName]:
                    segres = ctext['segres']

                    flag = False
                    if 'secondTemplateTypes' in ctext and tname in ctext['secondTemplateTypes']:
                        flag=True
                    if 'topTemplateTypes' in ctext and tname in ctext['topTemplateTypes']:
                        flag = True
                    if flag:
                        singleText = ctext

                        may_empty_fields=['segres_fg', 'auto_seg', "auto_seg_fg", "auto_time",
                                          "auto_loc", "auto_pos", "auto_bpres", "amr"]

                        for mef in may_empty_fields:
                            if mef not in singleText:
                                singleText[mef] = ""
                        
                        singleText['source'] = paper['testpaperName']

                        for tagField in sortedTagFieldsForTable:                            
                            if tagField[2] == "string":
                                if tagField[0] in singleText:
                                    singleText[tagField[0]] = singleText[tagField[0]]
                                else:
                                    singleText[tagField[0]] = ""
                            elif tagField[2] == "list_num":
                                if tagField[0] in singleText:
                                    info_str1 = ""
                                    info_str2 = ""
                                    for index in ctext[tagField[0]]:
                                        try:
                                            info_str1 += segres[int(index)] + " "
                                            info_str2 += str(index) + " "
                                        except:
                                            info_str2 += str(index) + " "

                                    ctext[tagField[0]] = info_str1 + "\n(" + info_str2 + ")"
                                else:
                                    singleText[tagField[0]] = ""
                            elif tagField[2] == "list_string_index":
                                if tagField[0] in singleText:
                                    singleText[tagField[0]] = " ".join([w+"/"+str(index) for w, index in zip(singleText[tagField[0]], range(len(singleText[tagField[0]])))])
                                else:
                                    singleText[tagField[0]] = ""
                            elif tagField[2] == "list_string":
                                if tagField[0] in singleText:
                                    singleText[tagField[0]] = " ".join(singleText[tagField[0]])
                                else:
                                    singleText[tagField[0]] = ""

                        if papertype == "choice":
                            singleText['number'] = str(question[questionIndexFieldName]) + "-" + singleText['number']
                        elif papertype == "subjective":
                            singleText['number'] = str(question[questionIndexFieldName]) + "-" + str(singleText['number'])

                        validList = ['template_valid', 'conpparse_valid', "auto_conpparse_valid", 'auto_template_valid']
                        for v in validList:
                            if v in ctext and ctext[v] == False:
                                ctext[v] = "false"
                            else:
                                ctext[v] = "true"

                        queryRes.append(singleText)

        #将queryRes转换成便于前端显示的形式
        tranformedRes = []
        textIndexes = []
        
        for res in queryRes:
            newres = []
            newres.append((True, res['source'], "source"))
            textIndexes.append(res[globalIndexFieldName])

            for field in sortedTagFieldsForTable:
                if field[3] == None:
                    newres.append((True, res[field[0]], field[0]))
                else:
                    if res[field[3]] == "true":
                        newres.append((True, res[field[0]], field[0]))
                    else:
                        newres.append((False, res[field[0]], field[0]))
            tranformedRes.append(newres)

        return render_to_response("BrowseByTemplate.html",
                                {'queryRes': zip(textIndexes,tranformedRes),
                                'sortedTagFieldsForTable': sortedTagFieldsForTable,
                                # remove 'Radio' at the end of this string
                                "templateSeltected": request.POST['template'][:-5],
                                'papertype': papertype,
                                'template_config': template_Info,
                                'template_config_json': json.dumps(template_Info),
                                'tagFields_config': tagFields_Info,
                                'tagFields_config_json': json.dumps(tagFields_Info)})

    elif request.method=="POST" and "outcontent" in request.POST:   #导出数据请求
        print "daochu"
        print request.POST
        templateNames=request.POST.getlist('outtemplate')   #模板名称,例如yyChk
        outcontents=request.POST.getlist('outcontent')   #导出内容,例如sourceChk

        #用来创建此次下载的临时文件夹（作为文件夹名的一部分）
        timestamp=time.time()
        timestamp=str(timestamp).replace(".","")
        #创建文件夹
        outPath="TestPaperData/DownloadData/"+timestamp+"./"
        os.mkdir(outPath)

        #模板缩写与模板中文名的对应词典
        tdict={}
        for t in template_Info:
            tdict[t[1]]=t[0].decode('utf-8')
        
        for template in templateNames:
            tag_tmpf=open(outPath+template+"."+papertype+".data","w")

            #写表头
            for index,content in enumerate(outcontents):
                if content=='sourceChk':
                    tag_tmpf.write(u'来源'.encode('utf-8'))
                else:
                    for tagField in tagFields_Info:
                        if content==tagField[0]+"Chk":
                            tag_tmpf.write(tagField[1])

                if index<len(outcontents)-1:
                    tag_tmpf.write("!@#")
            tag_tmpf.write('\n')

            #写标注信息
            template=template[:-3]

            papers=dataCollection.find()
            for paper in papers:
                for question in paper['Questions']:
                    for textInfo in question[textFieldName]:
                        flag=False
                        if 'topTemplateTypes' in textInfo and tdict[template] in textInfo['topTemplateTypes']:
                            flag=True
                        if 'secondTemplateTypes' in textInfo and tdict[template] in textInfo['secondTemplateTypes']:
                            flag=True

                        if flag==True:
                            for index,content in enumerate(outcontents):
                                if content=='sourceChk':
                                    tag_tmpf.write(paper['testpaperName'].encode('utf-8'))
                                elif content=="numberChk":
                                    if papertype=="choice":
                                        tag_tmpf.write(str(question[questionIndexFieldName])+"-"+textInfo['number'].encode('utf-8'))
                                    else:
                                        tag_tmpf.write(str(question[questionIndexFieldName])+"-"+str(textInfo['number']).encode('utf-8'))
                                else:
                                    for tagField in tagFields_Info:
                                        if content==tagField[0]+"Chk":
                                            #如果有依赖关系，进行判断，如果无效则不写入文件
                                            if tagField[3] != None and tagField[3] in textInfo and textInfo[tagField[3]] == False:
                                                tag_tmpf.write("")
                                            elif tagField[0] in textInfo and textInfo[tagField[0]] != None:
                                                if tagField[2] == "string":
                                                    try:
                                                        tag_tmpf.write(textInfo[tagField[0]].replace("\n", "").encode("utf-8"))
                                                    except:
                                                        textInfo[tagField[0]] = " ".join([str(x) for x in textInfo[tagField[0]]])
                                                        tag_tmpf.write(textInfo[tagField[0]].replace("\n", "").encode("utf-8"))
                                                elif tagField[2] == "list_num":
                                                    tag_tmpf.write(" ".join([str(i) for i in textInfo[tagField[0]]]).encode("utf-8"))
                                                elif tagField[2] == "list_string":
                                                    tag_tmpf.write(" ".join(textInfo[tagField[0]]).encode("utf-8"))
                                                elif tagField[2] == "list_string_index":
                                                    tag_tmpf.write(" ".join(textInfo[tagField[0]]).encode("utf-8"))
                                            else:
                                                tag_tmpf.write("")
                                                       
                                if index < len(outcontents)-1:
                                    tag_tmpf.write("!@#")
                            tag_tmpf.write("\n")

            tag_tmpf.close()

        #打包生成的所有文件
        source_dir = outPath
        buffer = StringIO.StringIO()
        z = zipfile.ZipFile(buffer,"w",zipfile.ZIP_DEFLATED)
        files = os.listdir(outPath)
        for f in files:
            file = open(outPath + f,'r')
            z.writestr(f,file.read())
            file.close()
        z.close()
        buffer.seek(0)
        
        # 返回压缩包文件
        response = HttpResponse(buffer.read())
        response['Content-Type'] = "application/x-zip"
        response['Content-Disposition'] = 'attachment; filename=' + timestamp + ".byTemplate." + papertype + ".zip"
        #response['Content-Length']=temp.tell()
        #temp.seek(0)
        
        # 删除未打包的文件夹
        shutil.rmtree(source_dir)
        
        return response

    elif request.method == 'GET':   # 开始查询之前
        default_template = None
        if papertype == "choice":
            default_template = "yy"
        else:
            default_template = "sdldwt"
        return render_to_response("BrowseByTemplate.html",
                                {'sortedTagFieldsForTable': sortedTagFieldsForTable,
                                 "templateSeltected": default_template,
                                 'papertype': papertype,
                                 'template_config': template_Info,
                                 'template_config_json': json.dumps(template_Info),
                                 'tagFields_config': tagFields_Info,
                                 'tagFields_config_json': json.dumps(tagFields_Info)})

