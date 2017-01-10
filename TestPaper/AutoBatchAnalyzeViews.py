#coding=utf-8
from django.shortcuts import render, render_to_response
from django.http import HttpResponse
import pymongo
import os,time
import mongoConnection

from . import geoProcessor

# Create your views here.
def autoBatchAnalyze(request):

    success_message=None
    times=None

    # 连接数据库
    conn = mongoConnection.connect_mongodb()

    GeopaperDB=conn['GeoPaper']

    if request.method=="POST":
        geo_processor=geoProcessor.geo_Processor()
        
        #给数据库上锁（/static文件夹下如果有一个mongo.lock的文件，就是mongodb整体被锁住了，这个锁只针对上传试卷的功能）

        #取锁
        while os.path.exists("static/mongo.lock"):
            continue

        #上锁
        f=open("static/mongo.lock","w")
        f.close()

        try:
            papertype=None
            papertype_chn=None
            dataCollection=None
            textFieldName=None
            state_document=None
            for key in request.POST:
                if "choice" in key:
                    papertype="choice"
                    papertype_chn=u"选择题"
                    dataCollection=GeopaperDB['ChoiceData']
                    state_document=GeopaperDB['globalData'].find_one({"auto_times":"choice"})
                    if state_document==None:
                        state_document={"auto_times":"choice"}
                    textFieldName="combinedTexts"
                    break
                elif "subjective" in key:
                    papertype="subjective"
                    papertype_chn=u"主观题"
                    dataCollection=GeopaperDB['SubjectiveData']
                    state_document=GeopaperDB['globalData'].find_one({"auto_times":"subjective"})
                    if state_document==None:
                        state_document={"auto_times":"subjective"}
                    textFieldName="subQuestions"
                    break
            
            papers=dataCollection.find().sort("uploadTimestamp", pymongo.DESCENDING)

            #分词
            if "seg_choice" in request.POST or "seg_subjective" in request.POST:
                seg_input_sentences=[]
                for paper in papers:             
                    if paper['States']['split']==False:
                        continue       
                    for question in paper['Questions']:
                        for ctext in question[textFieldName]:
                            if papertype=="choice":
                                seg_input_sentences.append("".join(ctext['text'].split()))
                            elif papertype=="subjective":
                                seg_input_sentences.append(ctext['text'])
               
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

                #将分词结果写入数据库
                papers=dataCollection.find().sort("uploadTimestamp",pymongo.DESCENDING)

                seg_index=0

                for paper in papers:
                    if paper['States']['split']==False:
                        continue
                    for question in paper['Questions']:
                        for ctext in question[textFieldName]:        
                            ctext["auto_seg"]=seg_output_sentences[seg_index]
                            ctext["auto_seg_fg"]=seg_output_sentences_fg[seg_index]
                            seg_index+=1              

                    dataCollection.save(paper)

                state_document['last_auto_seg_time_'+papertype]=time.strftime('%Y-%m-%d %H:%M:%S')
                GeopaperDB['globalData'].save(state_document)

                success_message=papertype_chn+u"批量分词完成"

            #实体、术语识别
            elif "entityTerm_choice" in request.POST or "entityTerm_subjective" in request.POST:
                fieldNames=['goldtimes','goldlocs','goldterms','goldquants']
                auto_fieldNames=["auto_time",'auto_loc','auto_term','auto_quant']
                names=['time',"loc","term","quant"]

                input_sentences=[]
                for paper in papers:
                    if paper['States']['seg']==False:
                        continue

                    for question in paper['Questions']:
                        for ctext in question[textFieldName]:
                            input_sentences.append(" ".join(ctext['segres']))

               
                segtl_output_sentences=geo_processor.process(input_sentences,4)        #接口4（分词结果-》含时间地点的分词）

                #对时间地点的结果进行处理
                AllSegStrs=[]

                All_tltq_lists=[]
                for n in names:
                    All_tltq_lists.append([])

                for s in segtl_output_sentences:
                    tag_lists=[]
                    for n in names:
                        tag_lists.append([])

                    tmpstr=""
                    s=s.decode("utf-8")
                    for index,w in enumerate(s.strip().split()):                                
                        if "_" in w:
                            tmpstr+=w.split("_")[0]+"_"+str(index)+" "
                            for i,n in enumerate(names):
                                if w.split("_")[1]==n:
                                    tag_lists[i].append(index)
                                    break
                            else:
                                print "error"
                                print w
                                return HttpResponse("出错了！")
                        else:
                            tmpstr+=w+"_"+str(index)+" "
                    AllSegStrs.append(tmpstr)

                    for i,atl in enumerate(All_tltq_lists):
                        atl.append(tag_lists[i])
                
                #将自动分析的时间地点放入数据库
                papers=dataCollection.find().sort("uploadTimestamp",pymongo.DESCENDING)

                index=0
                for paper in papers:
                    if paper['States']['seg']==False:
                        continue
                    for question in paper['Questions']:
                        for ctext in question[textFieldName]:
                            for i,afn in enumerate(auto_fieldNames):
                                ctext[afn]=All_tltq_lists[i][index]
                            index+=1
                    dataCollection.save(paper)

                state_document['last_auto_entityTerm_time_'+papertype]=time.strftime('%Y-%m-%d %H:%M:%S')
                GeopaperDB['globalData'].save(state_document)

                success_message=papertype_chn+u"批量实体术语识别完成（仅对完成了人工分词的试卷进行）"

            #词性标注
            elif "pos_choice" in request.POST or "pos_subjective" in request.POST:
                input_sentences=[]

                for paper in papers:
                    if paper['States']['seg']==False:
                        continue

                    for question in paper['Questions']:
                        for ctext in question[textFieldName]:
                            input_sentences.append(" ".join(ctext['segres']))

                #自动分词
                geo_processor=geoProcessor.geo_Processor()
                segpos_output_sentences=geo_processor.process(input_sentences,5)        #接口5（分词+时间地点-》词性）
                    
                papers=dataCollection.find().sort("uploadTimestamp",pymongo.DESCENDING)

                index=0
                for paper in papers:
                    if paper['States']['seg']==False:
                        continue
                    for question in paper['Questions']:
                        for ctext in question[textFieldName]:
                            ctext['auto_pos']=[p.split("_")[1] for p in segpos_output_sentences[index].split()]
                            index+=1
                    dataCollection.save(paper)

                state_document['last_auto_pos_time_'+papertype]=time.strftime('%Y-%m-%d %H:%M:%S')
                GeopaperDB['globalData'].save(state_document)

                success_message=papertype_chn+u"批量词性标注完成（仅对完成了人工分词的试卷进行）"

            #成分分析
            elif "bpres_choice" in request.POST or "bpers_subjective" in request.POST:
                input_sentences_goldseg=[]
                input_sentences_goldpos=[]        

                for paper in papers:
                    if paper['States']['pos']==False:
                        continue
                    for question in paper['Questions']:
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

                        tmpfile.write(s.encode("gbk")+"\t"+p.encode("gbk")+"\n")
                    tmpfile.write("\n")
                tmpfile.close()

                outfilename="SingleSentenceFiles/"+timestamp+".BerkeleyParser.out"
                
                cmd="java -Xmx1024m -jar nlptools/BerkeleyParser/berkeleyParser-1.7.jar -gr nlptools/BerkeleyParser/chn_sm5.gr -useGoldPOS <"+infilename+" >"+outfilename
                print cmd
                res=os.popen(cmd).readlines()


                #将自动分析的结果写回数据库
                papers=dataCollection.find().sort("uploadTimestamp",pymongo.DESCENDING)
               
                outfile=open(outfilename,"r")
                for paper in papers:
                    if paper['States']['pos']==False:
                        continue
                    for question in paper['Questions']:
                        for ctext in question[textFieldName]:            
                            ctext["auto_bpres"]=outfile.readline().decode("gbk").strip()
                            if "auto_conpparse_valid" in ctext:
                                del ctext['auto_conpparse_valid']

                    paper['States']['auto_bpres']=True
                    dataCollection.save(paper)
                outfile.close()

                #删除相关文件
                os.remove(infilename)
                os.remove(outfilename)

                state_document['last_auto_bpres_time_'+papertype]=time.strftime('%Y-%m-%d %H:%M:%S')
                GeopaperDB['globalData'].save(state_document)

                success_message=papertype_chn+u"批量句法分析完成（仅对完成了人工分词、词性标注的试卷进行）"
            
            #模板分析
            elif "template_choice" in request.POST or "template_subjective" in request.POST:
                input_text=[]
                input_seg=[]

                index=0
                #papers=dataCollection.find().sort("uploadTimestamp",pymongo.DESCENDING)
                pi=0
                for paper in papers:
                    pi+=1
                    if paper['States']['seg']==False:
                        continue
                    
                    for question in paper['Questions']:
                        for ctext in question[textFieldName]:
                            input_text.append(ctext['text'])
                            input_seg.append(ctext['segres'])
                            index+=1

                #自动生成模板信息（如果没有自动成分句法，还会生成自动句法分析结果）
                geo_processor=geoProcessor.geo_Processor()
                autoTemplate0=geo_processor.process_template(input_text,input_seg,papertype)

                #将自动分析结果写回数据库
                papers=dataCollection.find().sort("uploadTimestamp",pymongo.DESCENDING)

                index0=0
                pi=0
                for paperInfo in papers:
                    pi+=1
                    if paperInfo['States']['seg']==False:
                        continue
                    
                    for question in paperInfo['Questions']:
                        for ctext in question[textFieldName]:
                            ctext['auto_simplifiedTemplate']=autoTemplate0['auto_simplifiedTemplate'][index0]
                            ctext['auto_simplifiedTemplateTypes']=autoTemplate0['auto_simplifiedTemplateTypes'][index0]
                            ctext['auto_simplifiedTemplateCueword']=autoTemplate0['auto_simplifiedTemplateCueword'][index0]
                            ctext['auto_fullTemplate']=autoTemplate0['auto_fullTemplate'][index0]
                            ctext['auto_fullTemplateTypes']=autoTemplate0['auto_fullTemplateTypes'][index0]
                            ctext['auto_fullTemplateCueword']=autoTemplate0['auto_fullTemplateCueword'][index0]
                            index0+=1
                            if 'auto_template_valid' in ctext:
                                del ctext['auto_template_valid']

                    paperInfo['States']['autoTemplate']=True

                    dataCollection.save(paperInfo)

                state_document['last_auto_template_time_'+papertype]=time.strftime('%Y-%m-%d %H:%M:%S')
                GeopaperDB['globalData'].save(state_document)

                success_message=papertype_chn+u"批量模板分析完成（仅对完成了人工分词的试卷进行）"

        finally:
            #还锁
            os.remove("static/mongo.lock")

    choice_times=GeopaperDB['globalData'].find_one({"auto_times":"choice"})
    subjective_times=GeopaperDB['globalData'].find_one({"auto_times":"subjective"})
    times={}
    if choice_times!=None:
        times.update(choice_times)
    if subjective_times!=None:
        times.update(subjective_times)
    return render_to_response("./AutoBatchAnalyze.html",
                            {"success_message":success_message,
                            'times':times})
