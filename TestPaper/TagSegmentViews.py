#coding=utf-8
from django.shortcuts import render,render_to_response
from django.http import HttpResponse

import mongoConnection
import traceback

from . import geoProcessor

# Create your views here.
def tagSegment(request):
    # 连接数据库
    conn = mongoConnection.connect_mongodb()

    GeopaperDB=conn['GeoPaper']

    papername=request.GET['papername']
    papertype=request.GET['papertype']

    dataCollection=None
    textFieldName=None
    if papertype=="choice":
        dataCollection=GeopaperDB['ChoiceData']
        textFieldName="combinedTexts"
    elif papertype=="subjective":
        dataCollection=GeopaperDB['SubjectiveData']
        textFieldName="subQuestions"

    if request.method=="POST" and "generateSEG" in request.POST:  #生成候选分词结果
        paperInfo=None

        #读出原文本
        paperInfo=dataCollection.find_one({'testpaperName':papername})
        if not paperInfo:
            return HttpResponse("没有这份试卷")

        if paperInfo['States']['time']==True:
            return HttpResponse(u"<h1>本试卷已完成实体术语标注，不能再标注分词</h1><br><a href='./TagEachField.html?papername="+papername+u"'>前往单项标注页面</a>")

        seg_input_sentences=[]
        if papertype=="choice":
            for question in paperInfo['Questions']:
                for ctext in question['combinedTexts']:
                    seg_input_sentences.append("".join(ctext['text'].split()))
        elif papertype=="subjective":
            for question in paperInfo['Questions']:
                for q in question['subQuestions']:
                    seg_input_sentences.append(q['text'])

        #自动分词
        geo_processor=geoProcessor.geo_Processor()
        seg_output_sentences=geo_processor.process(seg_input_sentences,3)        #粗粒度，接口3（原文本-》含时间地点的分词）
        seg_output_sentences_fg=geo_processor.process(seg_input_sentences,2)     #细粒度，接口2（原文本-》纯分词）
        
        #对分词结果进行处理
        seg_output_sentences_withoutTL=[]
        for s in seg_output_sentences:
            s=s.decode("utf-8")
            removeTL=""
            for w in s.strip().split():
                if "_" in w:
                    removeTL+=w.split("_")[0]+" "
                else:
                    removeTL+=w+" "
            removeTL=removeTL[:-1]
            seg_output_sentences_withoutTL.append(removeTL)
        seg_output_sentences=seg_output_sentences_withoutTL            

        seg_output_sentences_fg=[s.strip() for s in seg_output_sentences_fg]


        #将分词结果写入数据库，并取出原文本
        texts=[]
        paperInfo=dataCollection.find_one({'testpaperName':papername})

        seg_index=0
        if papertype=="choice":
            for question in paperInfo['Questions']:
                for ctext in question['combinedTexts']:
                    texts.append(ctext['text'])           
                    ctext["auto_seg"]=seg_output_sentences[seg_index]
                    ctext["auto_seg_fg"]=seg_output_sentences_fg[seg_index]
                    seg_index+=1              
        elif papertype=="subjective":
            for question in paperInfo['Questions']:
                for subq in question['subQuestions']:
                    texts.append(subq['text'])
                    subq['auto_seg']=seg_output_sentences[seg_index]
                    subq['auto_seg_fg']=seg_output_sentences_fg[seg_index]
                    seg_index+=1

        #保存至数据库
        dataCollection.save(paperInfo)
        
        #返回自动分词结果给前端显示
        return render_to_response("TagSegment.html",
                                {'States':paperInfo['States'],
                                 "restype":"自动分词",
                                 "text_seg":zip(texts,seg_output_sentences,seg_output_sentences_fg),
                                 'papername':papername,
                                 'papertype':papertype})

    elif request.method == "POST" and "submitSEG" in request.POST:  #提交人工分词结果（含可能修改过的原试题文本）
        #print request.POST
        paperInfo = dataCollection.find_one({'testpaperName':papername})

        #保存标注者信息
        username = request.POST['username_name']
        paperInfo['relativeUsernames']['seg_tagger'] = username

        texts = []
        seg_res = []     #粗粒度
        seg_res_fg = []  #细粒度

        try:
            index = 0
            for question in paperInfo['Questions']:
                for ctext in question[textFieldName]:
                    if request.POST[str(index) + "_text"] != request.POST[str(index)+"_text_fg"]:
                        return HttpResponse("第" + index + "个文本的粗细粒度原文本不一致")
                    if len(request.POST[str(index) + "_text"].split("\t")) != 2:
                        return HttpResponse("第" + index + "个文本的粗粒度原文本中应该有一个tab隔开题面和选项")
                    if len(request.POST[str(index) + "_text_fg"].split("\t")) != 2:
                        return HttpResponse("第" + index + "个文本的细粒度原文本中应该有一个tab隔开题面和选项")

                    new_text = request.POST[str(index)+"_text"]   # 前端保证粗细粒度文本一致，这里只需获取一个
                    oritext = ctext['text']
                    if new_text != oritext:
                        ctext['text'] = new_text
                        if 'deprecated_text' in ctext:
                            ctext["deprecated_text"].append(new_text)
                        else:
                            ctext['deprecated_text'] = [new_text]
                    texts.append(new_text)

                    ctext['segres'] = request.POST[str(index) + "_seg"].split()
                    ctext['segres_fg'] = request.POST[str(index) + "_seg_fg"].split()
                    seg_res.append(" ".join(ctext['segres']))
                    seg_res_fg.append(" ".join(ctext['segres_fg']))
                    index += 1
        except Exception, e:
            print e
            print traceback.format_exc()
            print "提交失败，句子数目不一致"
            return HttpResponse("未知错误0")

        #修改试卷标注状态
        paperInfo['States']['seg']=True

        #保存至数据库
        dataCollection.save(paperInfo)

        return render_to_response("TagSegment.html",
                                {'seg_tagger':username,
                                 'States':paperInfo['States'],
                                 "restype":"人工分词",
                                 "text_seg":zip(texts,seg_res,seg_res_fg),
                                 'papername':papername,
                                 'papertype':papertype})


    else:   #直接显示页面     
        paperInfo=dataCollection.find_one({'testpaperName':papername})  

        username=None
        if "relativeUsernames" in paperInfo and 'seg_tagger' in paperInfo['relativeUsernames']:
            username=paperInfo['relativeUsernames']['seg_tagger']


        if not paperInfo:
            return HttpResponse("没有这份试卷")

        seg_res=[]
        seg_res_fg=[]
        texts=[]

        #如果有手动分词结果，则返回手动分词结果
        #否则，如果有自动分词结果，则返回自动分词结果
        #否则，返回原文本
        restype=""

        for question in paperInfo['Questions']:
            for ctext in question[textFieldName]:
                texts.append(ctext['text'])
                if 'segres' in ctext and ctext['segres']!=[]:
                    seg_res.append(" ".join(ctext['segres']))
                    restype=u"人工分词"
                elif 'auto_seg' in ctext:
                    seg_res.append(ctext['auto_seg'])
                    restype=u"自动分词"
                else:
                    if papertype=="choice":
                        seg_res.append("".join(ctext['text'].split()))
                    elif papertype=="subjective":
                        seg_res.append(ctext['text'])                
                    restype=u"无分词"
                
                if 'segres_fg' in ctext and ctext['segres_fg']!=[]:
                    seg_res_fg.append(" ".join(ctext['segres_fg']))
                elif 'auto_seg_fg' in ctext:
                    seg_res_fg.append(ctext['auto_seg_fg'])
                else:
                    if papertype=="choice":
                        seg_res_fg.append("".join(ctext['text'].split()))
                    elif papertype=="subjective":
                        seg_res_fg.append(ctext['text'])

        if username==None:
            return render_to_response("TagSegment.html",
                                    {'States':paperInfo['States'],
                                     "restype":restype,
                                     "text_seg":zip(texts,seg_res,seg_res_fg),
                                     'papername':papername,
                                     'papertype':papertype})
        else:
            return render_to_response("TagSegment.html",
                                    {'seg_tagger':username,
                                     'States':paperInfo['States'],
                                     "restype":restype,
                                     "text_seg":zip(texts,seg_res,seg_res_fg),
                                     'papername':papername,
                                     'papertype':papertype})

