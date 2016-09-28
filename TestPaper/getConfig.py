#coding=utf-8

#获取模板设置
def getTemplateConfig(papertype):
    template_file=open("static/geoTaggerConfig/"+papertype+"_template.txt")
    template_chinese=[]
    template_abbr=[]
    template_suggest=[]
    template_example=[]

    for l in template_file.readlines():
        if l.strip()=="":
            continue
        else:
            l=l.strip().split("\t")
            template_chinese.append(l[0])
            template_abbr.append(l[1])
            template_suggest.append(l[2])
            template_example.append(l[3])

    template_file.close()
    return zip(template_chinese,template_abbr,template_suggest,template_example)

def getNewTemplateConfig(papertype):
    if papertype=="choice":
        template_file = open("static/geoTaggerConfig/" + papertype + "_new_template.txt")
        template_chinese = []
        template_abbr = []
        template_level = []
        template_suggest = []
        template_example = []

        for l in template_file.readlines():
            if l.strip() == "":
                continue
            else:
                l = l.strip().split("\t")
                template_chinese.append(l[0])
                template_abbr.append(l[1])
                template_level.append(l[2])
                template_suggest.append(l[3])
                template_example.append(l[4])

        template_file.close()
        return zip(template_chinese, template_abbr, template_level, template_suggest, template_example)
    else:
        print "no new template config for subjective papertype"

def getTagFieldConfig(papertype):
    tagfield_file=open('static/geoTaggerConfig/'+papertype+"_tagfields.txt")
    tf_abbr=[]
    tf_chinese=[]
    tf_type=[]
    tf_validDepFlag=[]
    tf_tableWidth=[]
    tf_tableColIndex0=[]

    for l in tagfield_file.readlines():
        if l.strip()=="":
            continue
        else:
            l=l.strip().split("\t")
            tf_abbr.append(l[0])
            tf_chinese.append(l[1])
            tf_type.append(l[2])
            if l[3]=="null":
                tf_validDepFlag.append(None)
            else:
                tf_validDepFlag.append(l[3])
            tf_tableWidth.append(l[4])
            tf_tableColIndex0.append(int(l[5]))

    tagfield_file.close()

    return zip(tf_abbr,tf_chinese,tf_type,tf_validDepFlag,tf_tableWidth,tf_tableColIndex0)

def getShowStateFieldConfid(papertype):
    showStateField_file=open('static/geoTaggerConfig/'+papertype+'_showState_fields.txt')

    ssf_abbr=[]
    ssf_chinese=[]
    ssf_newline=[]

    for l in showStateField_file.readlines():
        if l.strip()=="":
            continue
        else:
            l=l.strip().split("\t")
            ssf_abbr.append(l[0])
            ssf_chinese.append(l[1])
            ssf_newline.append(l[2])
    
    showStateField_file.close()
    return zip(ssf_abbr,ssf_chinese,ssf_newline)