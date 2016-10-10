#coding=utf-8
import os


def transformSQLChoiceFile(sqlfile):
    content = open(sqlfile).read().decode("utf-8")

    bgtext = 2
    qtext = 8
    choiceStart = 9
    isMulti = 13
    smallChoiceStart = 14
    pdesc = 29

    datalines = content.split("\n")

    file_contents = []
    file_names = []

    choicesName=["A","B","C","D"]
    smallChoicesName=u"①②③④⑤⑥⑦⑧⑨"

    last_paperName = None
    paperContent = []
    last_bgtext_str = None
    bgtext_index = 0
    question_index = 1
    for line in datalines:
        if line.strip()=="":
            continue
        line = line.split("\t")
        paperName = line[pdesc]
        if paperName!=last_paperName:
            if last_paperName!=None:
                file_names.append(last_paperName)
                file_contents.append("\n".join(paperContent))
                last_paperName = paperName
                paperContent = []
                bgtext_index = 0
                question_index = 1
            else:
                last_paperName = paperName

        # generate new bgtext line
        bgtext_str = line[bgtext]
        if bgtext_str!="" and bgtext_str!=last_bgtext_str:
            bgtext_index+=1
            last_bgtext_str = bgtext_str
            paperContent.append(str(bgtext_index)+"-\t"+bgtext_str)

        # generate timian line
        if bgtext_str == "":
            paperContent.append("-"+str(question_index)+"\t"+line[qtext].replace(" ","").replace(",",u"，"))
        else:
            paperContent.append(str(bgtext_index)+"-"+str(question_index)+"\t"+line[qtext].replace(" ","").replace(",",u"，"))

        # generate choice line
        if line[isMulti]=="0":
            for i in range(4):
                paperContent.append(str(question_index)+"-"+choicesName[i]+"\t"+line[choiceStart+i].replace(" ","").replace(",",u"，"))
        else:
            for i in range(9):
                if line[smallChoiceStart+i]=="":
                    continue
                paperContent.append(str(question_index)+"-"+smallChoicesName[i]+"\t"+line[smallChoiceStart+i].replace(" ","").replace(",",u"，"))
            for i in range(4):
                paperContent.append(str(question_index)+"-"+choicesName[i]+"\t"+line[choiceStart+i].replace(" ","").replace(",",u"，"))

        question_index+=1

    file_names.append(last_paperName)
    file_contents.append("\n".join(paperContent))

    if not os.path.exists("transform_data"):
        os.mkdir("transform_data")

    for fname,fcontent in zip(file_names,file_contents):
        fout = open("transform_data/"+fname+".txt","w")
        fout.write(fcontent.encode("utf-8"))
        fout.close()

transformSQLChoiceFile("CQs.txt")


