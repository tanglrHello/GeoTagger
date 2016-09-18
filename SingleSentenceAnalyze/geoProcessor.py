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
        
        cmd="java -jar nlptools/cws_tag_file/Geo_3pra.jar "+str(typeIndex)+" nlptools/cws_tag_file/ "+timestamp+"_"+str(typeIndex)
        
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
