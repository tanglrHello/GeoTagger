#coding=utf-8
from django.http import HttpResponseRedirect

def homepage(request):
	return HttpResponseRedirect('/TestPaper/BrowseByPaper?&papertype=choice')