#coding=utf-8
import time,os

class geo_Processor():
    def process(self,sentence,typeIndex):
        timestamp=time.time()
        starttime=timestamp
        timestamp=str(timestamp).replace(".","")
        #infilename=u"SingleSentenceFiles/"+unicode(timestamp)+u".geo.in"
        #outfilename=u"SingleSentenceFiles/"+unicode(timestamp)+u".geo.out"
        
        infiledir="nlptools/cws_tag_file/data/"
        infilename=timestamp+"_"+str(typeIndex)+"_input.txt"
        outfiledir="nlptools/cws_tag_file/data/"
        outfilename=timestamp+"_"+str(typeIndex)+"_output.txt"

        
        #write sentence to infile
        infile=open(infiledir+infilename,"w")
        for s in sentence:
            infile.write(s.encode("utf-8")+"\n")
        infile.close()
        
        cmd="java -Xmx2g -jar nlptools/cws_tag_file/Geo_3pra.jar "+str(typeIndex)+" nlptools/cws_tag_file/ "+timestamp+"_"+str(typeIndex)
        
        print "runcommand_geoProcessor"
        print cmd
        res=os.popen(cmd).readlines()
        print res
        print "command output:"
        print "command output end."

        resfile=open(outfiledir+outfilename,'r')
        res=resfile.readlines()
        resfile.close()

        #delete files
        os.remove(infiledir+infilename)
        os.remove(outfiledir+outfilename)

        print (time.time()-starttime)

        return res

    def process_template(self,texts,segs,papertype):
        timestamp=time.time()
        timestamp=str(timestamp).replace(".","")

        infiledir="nlptools/geo_templateTagger/data/"
        infilename=timestamp+"_"+papertype+"_input.txt"
        outfiledir="nlptools/geo_templateTagger/data/"
        outfilename=timestamp+"_"+papertype+"_output.txt"

        #write infos into infile
        infile=open(infiledir+infilename,"w")

        for text in texts:
            infile.write(text.encode("utf-8")+"\n")
        infile.close()

        cmd="java -Dfile.encoding=utf-8 -jar nlptools/geo_templateTagger/Templating.jar "+papertype+" "+infilename
        print "runcommand_geoProcessor_templateTagger"
        print cmd
        res=os.popen(cmd).readlines()
        #print res
        #print "command output:"
        print "command end."

        
        autoTemplate={}
        templateInfoNames=['auto_simplifiedTemplate',
                            'auto_simplifiedTemplateTypes',
                            'auto_simplifiedTemplateCueword',
                            'auto_fullTemplate',
                            'auto_fullTemplateTypes',
                            'auto_fullTemplateCueword']

        for tn in templateInfoNames:
            autoTemplate[tn]=[]

        resfile=open(outfiledir+outfilename,'r')
        #resfile=open("nlptools/geo_templateTagger/data/146478715776_choice_output.txt")
        res=resfile.readlines()
        resfile.close()

        autoTemplate['auto_simplifiedTemplate']=[t.strip().decode('utf-8') for i,t in enumerate(res) if i%4==0]
        stt=[t.strip().decode('utf-8') for i,t in enumerate(res) if i%4==1]
        autoTemplate['auto_fullTemplate']=[t.strip().decode('utf-8') for i,t in enumerate(res) if i%4==2]
        ftt=[t.strip().decode('utf-8') for i,t in enumerate(res) if i%4==3]

        noCuewordTemplate=[u"实体信息陈述",u"一般陈述",u"时间限定"]
        for tt in stt:
            templateTypes=[]
            templateCuewords=[]
            for ti in tt.split():
                ti=ti.split("_")
                templateTypes.append(ti[0])
                if ti[0] not in noCuewordTemplate:
                    templateCuewords.append(ti[1]+"_")

            autoTemplate['auto_simplifiedTemplateTypes'].append(list(set(templateTypes)))
            autoTemplate['auto_simplifiedTemplateCueword'].append(templateCuewords)
 
        for tt in ftt:
            templateTypes=[]
            templateCuewords=[]
            for ti in tt.split():
                ti=ti.split("_")
                templateTypes.append(ti[0])
                if ti[0] not in noCuewordTemplate:
                    templateCuewords.append(ti[1]+"_")

            autoTemplate['auto_fullTemplateTypes'].append(list(set(templateTypes)))
            autoTemplate['auto_fullTemplateCueword'].append(templateCuewords)            

        #delete files
        
        os.remove(infiledir+infilename)
        os.remove(outfiledir+outfilename)
        os.remove(outfiledir+outfilename[:-10]+"log.txt")
        

        return autoTemplate

    
    def get_seg_res(self,s):
        s=s.split();
        seg_res=[t.split('_')[0] for t in s]
        #for term in seg_res:
        seg_res=[t+"_"+str(index) for index,t in enumerate(seg_res)]
        return "  ".join(seg_res)
            
    def get_pos_res(self,s):
        s=s.split()
        pos_res=[t.split("_")[1] for t in s]
        pos_res=[t+"_"+str(index) for index,t in enumerate(pos_res)]
        return "  ".join(pos_res)
    
    def get_entityTerm_res(self,s,typestr):
        s=s.split()
        time_res=[]
        for index,t in enumerate(s):
            t=t.split("_")
            if t[1]==typestr:
                time_res.append(t[0]+"_"+str(index))
        res="  ".join(time_res)
        if res=="":
            return "(null)"
        else:
            return res
    
    def get_time_res(self,s):
        s=s.split()
        time_res=[]
        for index,t in enumerate(s):
            t=t.split("_")
            if t[1]=="time":
                time_res.append(t[0]+"_"+str(index))
        res="  ".join(time_res)
        if res=="":
            return "(null)"
        else:
            return res
    
    def get_loc_res(self,s):
        s=s.split()
        loc_res=[]
        for index,t in enumerate(s):
            t=t.split("_")
            if t[1]=="loc":
                loc_res.append(t[0]+"_"+str(index))
        res="  ".join(loc_res)
        if res=="":
            return "(null)"
        else:
            return res