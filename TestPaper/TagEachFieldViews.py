#coding=utf-8
from django.shortcuts import render_to_response
import mongoConnection

# Create your views here.
def tagEachField(request):
    # 连接数据库
    conn = mongoConnection.connect_mongodb()

    GeopaperDB=conn['GeoPaper']

    papertype = None
    if 'papertype' not in request.GET:
        papertype="choice"
    else:
        papertype=request.GET['papertype']

    dataCollection=None
    papertype_chn=None
    if papertype=="choice":
        papertype_chn="选择题"
        dataCollection=GeopaperDB['ChoiceData']
    elif papertype=="subjective":
        papertype_chn="主观题"
        dataCollection=GeopaperDB['SubjectiveData']

    papername=request.GET['papername']
    paperInfo=dataCollection.find_one({'testpaperName':papername})
    States=paperInfo['States']

    return render_to_response("TagEachField.html",
                            {'papername':papername,
                             'States':States,
                             'papertype':papertype,
                             'papertype_chn':papertype_chn})
    