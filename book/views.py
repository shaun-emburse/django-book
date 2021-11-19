import logging
import urllib.parse

from django import forms
from django.http import HttpResponseRedirect
from django.http.response import HttpResponse, JsonResponse
from django.shortcuts import render

from olclient.openlibrary import OpenLibrary

from .forms import AuthorForm, ConfirmAuthorForm, TitleForm, TitleGivenAuthorForm, ConfirmBook
from .models import Author

logger = logging.getLogger(__name__)

def get_author(request):
    """ Render a form requesting author name, then redirect to confirmation of details """
    if request.method == 'POST':
        form = AuthorForm(request.POST)
        if form.is_valid():
            # Send to a page which will attempt to look up this author name and confirm the selection
            name = form.cleaned_data['author_name']
            return HttpResponseRedirect(f'/confirm-author.html?author_name={name}')
    form = AuthorForm()
    return render(request, 'author.html', {'form': form})

def confirm_author(request):
    """ Do a lookup of this author by the name sent and display and confirm details from OpenLibrary """
    if request.method == 'GET':
        name = request.GET['author_name']
        ol = OpenLibrary()
        results = ol.Author.search(name, 2)
        first_author = results[0]
        second_author = results[1]
        first_olid = first_author['key'][9:]  # remove "/authors/" prefix
        second_olid = second_author['key'][9:]
        existing_author = Author.objects.filter(olid=first_olid).exists()
        form = ConfirmAuthorForm({'author_olid' :first_olid, 'author_name': first_author['name']})
        # NOTE: adding this because sometimes even with full name first result is wrong
        form2 = ConfirmAuthorForm({'author_olid': second_olid, 'author_name': second_author['name']})
        return render(request, 'confirm-author.html', {'form': form, 'form2': form2})
    if request.method == 'POST':
        # This is a confirmed author. Ensure that they have been recorded.
        name = request.POST['author_name']
        olid = request.POST['author_olid']

        author_lookup_qs = Author.objects.filter(olid=olid)
        if not author_lookup_qs:
            Author.objects.create(
                
            )
        

        # Finally, redirect them off to the title lookup
        return HttpResponseRedirect(f'/title.html?author_olid={olid}&author_name={name}')

def get_title(request):
    """ Do a lookup of a book by title, with a particular author potentially already set """
    logger.error("get title")
    if request.method == 'GET':
        if 'author_olid' in request.GET:
            a_olid = request.GET['author_olid']
            form = TitleGivenAuthorForm({'author_olid': a_olid, 'author_name': request.GET['author_name']})
            # Attempting to override with runtime value for url as a kludge for how to pass the author OLID
            data_url = "/author/" + a_olid +  "/title-autocomplete"
            logger.error("new data url %s", data_url)
            form.fields['title'].widget=forms.TextInput(attrs={'autofocus': 'autofocus',
                'class': 'basicAutoComplete',
                'data-url': data_url,
                'autocomplete': 'off'})
        else:
            form = TitleForm()
        return render(request, 'title.html', {'form': form})
    if request.method == 'POST':
        return HttpResponseRedirect(f"/confirm-book.html?title={request.POST['title']}&author_olid={request.POST['author_olid']}&author_name={request.POST['author_name']}")

def confirm_book(request):
    """ Given enough information for a lookup, retrieve the most likely book and confirm it's correct """
    # Build the link back to the author page
    params = {}
    params = request.GET if request.method == 'GET' else params
    params = request.POST if request.method == 'POST' else params
    if 'title' not in params:
        return HttpResponse('Title required')
    title = params['title']
    author = None  # search just on title if no author chosen
    args = {}
    author_olid = None
    if 'author_name' in params:  # use author name as default if given; save in context
        author=params['author_name']
        args['author_name'] = author
    if 'author_olid' in params:  # prefer OpenLibrary ID if specified
        author_olid=params['author_olid']
        args['author_olid'] = author_olid
        author = author_olid
    context = {'title_url': "title.html?" + urllib.parse.urlencode(args)}

    # Build display of book
    ol = OpenLibrary()
    result = ol.Work.search(author=author, title=title)
    # TODO: This selects the first author, but should display multiple authors, or at least prefer the specified author
    author_name = result.authors[0]['name']
    args['title'] = result.title
    args['work_olid'] = result.identifiers['olid'][0]
    context['form'] = ConfirmBook(args)
    context['author_name'] = author_name

    # Display confirmation form, or
    if request.method == 'GET':
        return render(request, 'confirm-book.html', context)
    # Process confirmation and direct to next step
    elif request.method == 'POST':
        # TODO: Actually save the book here
        return render(request, 'just-entered-book.html', context)

def author_autocomplete(request):
    """ Return a list of autocomplete suggestions for authors """
    # TODO: First attempt to select from authors already in library locally
    # TODO: Add ability to suggest authors with zero characters
    # TODO: Sort authors by number of books by them in the local library
    # Initial version: return the suggestions from OpenLibrary
    RESULTS_LIMIT = 5
    if 'q' in request.GET:
        ol = OpenLibrary()
        authors = ol.Author.search(request.GET['q'], RESULTS_LIMIT)
        names = [author['name'] for author in authors]
        return JsonResponse(names, safe=False)  # safe=False required to allow list rather than dict

def title_autocomplete(request, oid):
    """
    Returns an autocomplete suggestion for the work
    Narrows down by author specified by oid
    """
    if 'q' in request.GET:
        ol = OpenLibrary()
        result = ol.Work.search(author=oid, title=request.GET['q'])
        names = [result.title]
        return JsonResponse(names, safe=False)  # safe=False required to allow list rather than dict

def test_autocomplete(request):
    """ Test page from the bootstrap autocomplete repo to figure out how to get dropdowns working right """
    return render(request, 'test-autocomplete.html')
