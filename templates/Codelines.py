#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""代码行统计工具，支持Python 2.x/3.x
最简单的用法就是拷贝此文件到源代码目录，直接双击执行，
如果带一个参数，则是要分析的目录名，
第二个参数之后的各参数则是要排除的文件或目录列表，目录中有空格则需要使用引号括起来
"""
import os, sys, locale

try:
    import chardet
except ImportError:
    try:
        import charade as chardet
    except ImportError:
        chardet = None

class CountInfo:
    def __init__(self, fileName, lineCount = 0, commentLineCount = 0, blankLineCount = 0, byteCount = 0):
        self.fileName = fileName
        self.fileCount = 0
        self.lineCount = lineCount
        self.commentLineCount = commentLineCount
        self.blankLineCount = blankLineCount
        self.byteCount = byteCount

def getFileLines(fn):
    try:
        with open(fn, 'rb') as f:
            d = f.read()
    except:
        print(' Open failed: %s.' % fn)
        return []

    try:
        lines = d.decode('utf-8').split('\n')
    except:
        if chardet:
            lines = d.decode(chardet.detect(d)['encoding']).split('\n')
        else:
            try:
                lines = d.decode(locale.getpreferredencoding())
            except:
                print(' Decode failed: %s.' % fn)
                return []
    return lines

class LineCounter:
    COUNTER_TYPE = None

    def __init__(self, manager):
        self.manager = manager
        if self.COUNTER_TYPE:
            self.manager.registerLineCounter(self.COUNTER_TYPE, self)

    def doCount(self, fileName):
        info = CountInfo(fileName)
        self.isInAnnotation = False

        lines = getFileLines(fileName)
        for line in lines:
            sline = line.strip()
            if sline == '':
                info.blankLineCount += 1
            elif self.isCommentLine(sline):
                info.commentLineCount += 1
            else:
                info.lineCount += 1

        info.byteCount += os.path.getsize(fileName)
        self.manager.appendCountInfo(info)
        return info

    def isCommentLineCppStyle(self, line):
        if not self.isInAnnotation:
            if line.startswith("//"):
                return True
            elif line.startswith("/*") and line.endswith("*/"):
                return True
            elif line.startswith("/*"):
                self.isInAnnotation = True
                return True
            else:
                return False
        else:
            if line.endswith("*/"):
                self.isInAnnotation = False
            return True

class TextLineCounter(LineCounter):
    COUNTER_TYPE = 'text'

    def isCommentLine(self, line):
        return False

class XmlLineCounter(LineCounter):
    COUNTER_TYPE = 'xml'

    def isCommentLine(self, line):
        return False

class CppLineCounter(LineCounter):
    COUNTER_TYPE = 'cpp'

    def __init__(self, manager):
        LineCounter.__init__(self, manager)
        self.isCommentLine = self.isCommentLineCppStyle

class PythonLineCounter(LineCounter):
    COUNTER_TYPE = 'python'

    def isCommentLine(self, line):
        if not self.isInAnnotation:
            if line.startswith("#"):
                return True
            elif line.startswith("'''") and line.endswith("'''"):
                return True
            elif line.startswith('"""') and line.endswith('"""'):
                return True
            elif line.startswith("'''") or line.startswith('"""'):
                self.isInAnnotation = True
                self.expectStopAnnotation = line[:3]
                return True
            else:
                return False
        else:
            if line.endswith(self.expectStopAnnotation):
                self.isInAnnotation = False
            return True

class CountManager:
    def __init__(self):
        self.fsTypeDict = {}
        #self.fsTypeDict['.txt'] = 'text'
        self.fsTypeDict['.sql'] = 'text'
        self.fsTypeDict['.xml'] = 'xml'
        self.fsTypeDict['.jsp'] = 'xml'
        self.fsTypeDict['.wml'] = 'xml'
        self.fsTypeDict['.htm'] = 'xml'
        self.fsTypeDict['.html'] = 'xml'
        self.fsTypeDict['.js'] = 'cpp'
        self.fsTypeDict['.cs'] = 'cpp'
        self.fsTypeDict['.java'] = 'cpp'
        self.fsTypeDict['.cpp'] = 'cpp'
        self.fsTypeDict['.c'] = 'cpp'
        self.fsTypeDict['.h'] = 'cpp'
        self.fsTypeDict['.hpp'] = 'cpp'
        self.fsTypeDict['.py'] = 'python'
        self.fsTypeDict['.tac'] = 'python'

        self.countInfoDict = {}

        self.countDict = {}
        self.counters = []
        self.counters.append(TextLineCounter(self))
        self.counters.append(XmlLineCounter(self))
        self.counters.append(CppLineCounter(self))
        self.counters.append(PythonLineCounter(self))
        self.countInfoList = []
        self.TotalCountInfo = CountInfo("Total")

    def registerLineCounter(self, type, counter):
            self.countDict[type] = counter
            for key in self.fsTypeDict.keys():
                    if self.fsTypeDict[key] == type:
                            self.fsTypeDict[key] = counter

    def getCounter(self, extension):
        if extension in self.fsTypeDict:
            return self.fsTypeDict[extension]
        else:
            return None

    def appendCountInfo(self, info):
        (f_, ext) = os.path.splitext(info.fileName)
        extension = ext.lower()
        if extension in self.countInfoDict.keys():
            currCountInfo = self.countInfoDict[extension]
        else:
            currCountInfo = CountInfo(extension)
            self.countInfoDict[extension] = currCountInfo

        currCountInfo.fileCount += 1
        currCountInfo.lineCount += info.lineCount
        currCountInfo.commentLineCount += info.commentLineCount
        currCountInfo.blankLineCount += info.blankLineCount
        currCountInfo.byteCount += info.byteCount

        self.TotalCountInfo.fileCount += 1
        self.TotalCountInfo.lineCount += info.lineCount
        self.TotalCountInfo.commentLineCount += info.commentLineCount
        self.TotalCountInfo.blankLineCount += info.blankLineCount
        self.TotalCountInfo.byteCount += info.byteCount
        self.countInfoList.append(info)

    def dispCountInfo(self):
        print("-------------------------------------------------------------------------------")
        print("%-8s  %-8s  %-8s  %-8s  %-8s   %-8s   %-8s" % 
            ("Type", "Files", "Code", "Comment", "Comment/Code", "Blank", "Bytes/Line"))
        print("-------------------------------------------------------------------------------")
        for key in self.countInfoDict:
            countInfo = self.countInfoDict[key]
            if countInfo.lineCount > 0:
                commentRate = (100 * float(countInfo.commentLineCount) / countInfo.lineCount)
            else:
                commentRate = 0.0
            print("%-8s  %-8d  %-8d  %-8d  %-4.1f %%         %-8d   %.1f" % 
                (countInfo.fileName, countInfo.fileCount,
                countInfo.lineCount, countInfo.commentLineCount,
                commentRate,
                countInfo.blankLineCount,
                float(countInfo.byteCount) / (countInfo.lineCount +
                        countInfo.commentLineCount + countInfo.blankLineCount)))
        print("-------------------------------------------------------------------------------")
        if self.TotalCountInfo.lineCount > 0:
            commentRate = (100 * float(self.TotalCountInfo.commentLineCount) / self.TotalCountInfo.lineCount)
        else:
            commentRate = 0.0
        allCount = self.TotalCountInfo.lineCount+self.TotalCountInfo.commentLineCount+self.TotalCountInfo.blankLineCount
        print("%-8s  %-8d  %-8d  %-8d  %-4.1f %%         %-8d   %.1f" % \
            ("Total", self.TotalCountInfo.fileCount,
            self.TotalCountInfo.lineCount, self.TotalCountInfo.commentLineCount,
            commentRate,
            self.TotalCountInfo.blankLineCount,
            float(self.TotalCountInfo.byteCount) / allCount if allCount else 0))

ignores = ('.doc', '.docx', '.xls', '.ppt', '.mpp', '.pdf',
           '.db', '.dbf', '.log'
           '.jpg', '.jpeg', '.png', '.bmp', '.gif', '.ico', 'icon', '.swf',
           '.svn-base',
           '.jar', '.class',
           '.rar', '.zip', '.7z',
           '.resx', '.csproj', '.obj', '.bak', '.jude',
           '.txt', '.pro', '.pyc', '.pyd', '.pyo', '.exe', '.dll',
           '.bat','.md','.ini','.qm','.ts','.qrc','.tpl'
           )

errors = []

def CountDirs(DirName, excludes):
    NumberFiles = 0
    NumberDirectories = 0
    manager = CountManager()
    for root, dirs, files in os.walk(DirName):
        NumberDirectories += 1
        for file_name in files:
            (f_, ext) = os.path.splitext(file_name)
            extension = ext.lower().strip()
            if extension == '':
                continue
            counter = manager.getCounter(extension)
            if not counter:
                if (extension  not in ignores) and (extension not in errors):
                        errors.append(extension)
                continue
            real_file = os.path.join(root, file_name).replace('\\','/')
            for ex in excludes:
                if real_file.lower().startswith(ex):
                    print(' Excluded: %s' % real_file)
                    break
            else:
                info = counter.doCount(real_file)
                print(" %s ==> %d:%d:%d" % (real_file, info.lineCount, info.commentLineCount, info.blankLineCount))
    print('\n')
    manager.dispCountInfo()
    if len(errors) > 0:
            print("\nUnknown Extension: %s\n" % ','.join(errors))

if __name__ == "__main__":
    excludes = [os.path.abspath(__file__).lower().replace('\\','/')]
    if len(sys.argv) <= 1:
        ScanDir = os.getcwd()
    elif len(sys.argv) >= 2:
        ScanDir = os.path.abspath(sys.argv[1])
        if len(sys.argv) > 2:
            for d in sys.argv[2:]:
                d = os.path.abspath(d).replace('\\','/')
                if os.path.isdir(d) and not d.endswith('/'):
                    d += '/'
                excludes.append(d.lower())

    CountDirs(ScanDir, excludes)
    os.system('pause')
