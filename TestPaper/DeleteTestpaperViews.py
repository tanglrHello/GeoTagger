#coding=utf-8
from django.http import HttpResponse,HttpResponseRedirect
from django.shortcuts import render_to_response
import mongoConnection
import os

def deleteTestpaper(request):
    # 连接数据库
    conn = mongoConnection.connect_mongodb()
    geoData=conn['GeoPaper']

    papername=request.GET.get("papername")
    papertype=request.GET.get("papertype")

    paperDB=None
    filepath=None
    papertype_chn=None
    if papertype=="choice":
        paperDB=geoData['ChoiceData']
        papertype_chn="选择题"
        filepath="TestPaperData/ChoiceData/"
    elif papertype=="subjective":
        paperDB=geoData['SubjectiveData']
        papertype_chn="主观题"
        filepath="TestPaperData/SubjectiveData/"

    paperInfo=paperDB.find_one({'testpaperName':papername})


    if paperInfo==None:
        return HttpResponse(u"<h1>非法访问，没有相应试卷信息！</h1><br><a href='./BrowseByPaper.html?papertype="+papertype+u"'>返回试卷列表页面</a>")
    else:
        if request.method=="POST":
            delpwd=request.POST.get("delpwd")
            if delpwd=="quedingshanchu":
                #删除数据库记录
                paperDB.remove({'testpaperName':papername})
                #删除试卷文本文件
                os.remove(filepath+papername+".txt")
                return HttpResponseRedirect("./BrowseByPaper.html?papertype="+papertype)
            else:
                return render_to_response("./DeleteTestpaper.html",
                                         {'error_msg':"删除密码错误!",
                                        'papertype':papertype_chn,
                                        'papername':papername})

        else:
            return render_to_response("./DeleteTestpaper.html",
                                        {'papertype':papertype_chn,
                                        'papername':papername})

    
