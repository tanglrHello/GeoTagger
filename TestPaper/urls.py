from django.conf.urls import url
from django.contrib import admin
from . import AddTestPaperViews,BrowseByPaperViews,BrowseByTemplateViews
from . import TagSentenceViews,TagSplitViews,TagEachFieldViews
from . import TagSegmentViews,TagTimeLocViews,TagPosViews,TagConpparseViews,TagTermViews
from . import TagTemplateViews,TagNewTemplateViews
from . import PosReferenceViews
from . import TestpaperInfoViews,DeleteTestpaperViews
from . import SearchTextViews,AutoBatchAnalyzeViews
from . import TagQuestionViews,TagBackgroundViews, TagAMRViews
from . import StatisticViews
from . import homepageViews

urlpatterns = [
    url(r'AddTestPaper',AddTestPaperViews.addTestPaper),
	url(r'BrowseByPaper',BrowseByPaperViews.browseByPaper),
	url(r'BrowseByTemplate',BrowseByTemplateViews.browseByTemplate),
	url(r'TagSentence',TagSentenceViews.tagSentence),
    url(r'TagEachField',TagEachFieldViews.tagEachField),
    url(r'TagSegment',TagSegmentViews.tagSegment),
    url(r'TagTimeLoc',TagTimeLocViews.tagTimeLoc),
    url(r'TagTerm',TagTermViews.tagTerm),
    url(r'TagPos',TagPosViews.tagPos),
    url(r'PosReference',PosReferenceViews.posReference),
    url(r'TagConpparse',TagConpparseViews.tagConpparse),
    url(r'TagAMR', TagAMRViews.tagAMR),
    url(r'TagTemplate',TagTemplateViews.tagTemplate),
    url(r'TagNewTemplate',TagNewTemplateViews.tagNewTemplate),
	url(r'TagSplit',TagSplitViews.tagSplit),
	url(r'TestpaperInfo',TestpaperInfoViews.testpaperInfo),
	url(r'DeleteTestpaper',DeleteTestpaperViews.deleteTestpaper),
    url(r'SearchText',SearchTextViews.searchText),
    url(r'AutoBatchAnalyze',AutoBatchAnalyzeViews.autoBatchAnalyze),
    url(r'TagBackground',TagBackgroundViews.tagBackground),
    url(r'TagQuestion',TagQuestionViews.tagQuestion),
    url(r'Statistic',StatisticViews.statistic),
    url(r'index',homepageViews.homepage)
]
