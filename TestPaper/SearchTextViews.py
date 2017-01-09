#coding=utf-8
from django.shortcuts import render,render_to_response
import mongoConnection


# Create your views here.
def searchText(request):
    if request.method=="POST":   #检索试题请求
        # 连接数据库
        conn = mongoConnection.connect_mongodb()

        GeopaperDB=conn['GeoPaper']

        choiceCollection=GeopaperDB['ChoiceData']
        subjectiveCollection=GeopaperDB['SubjectiveData']

        relativeTexts=[]

        kw=request.POST['query_kw_name']


        for paper in choiceCollection.find():
            for question in paper['Questions']:
                for ctext in question['combinedTexts']:
                    if kw in ctext['text']:                        
                        relativeTexts.append([paper['testpaperName'],\
                                                    u"选择题",\
                                                    u"choice",\
                                                    str(question['QuestionIndex'])+u"-"+ctext['number'],\
                                                    str(ctext['combinedChoiceIndex']),\
                                                    ctext['text']])

        for paper in subjectiveCollection.find():
            for question in paper['Questions']:
                for ctext in question['subQuestions']:
                    if kw in ctext['text']:
                        relativeTexts.append([paper['testpaperName'],\
                                                    u"主观题",\
                                                    u"subjective",\
                                                    str(question['number'])+u"-"+str(ctext['number']),\
                                                    str(ctext['subQuestionIndex']),\
                                                    ctext['text']])

        return render_to_response("./SearchText.html",
                                {'relativeTexts':relativeTexts,
                                "query_kw":kw})

    else:  #直接打开页面
        return render_to_response("./SearchText.html")
