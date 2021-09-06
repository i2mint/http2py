[Documentation here](https://i2mint.github.io/http2py/)

`the_one_where_we_have_an_http_service_that_we_want_call_through_normal_looking_python_functions`

# (Http) Requests for humans

Tools to create python binders to http web services.
Here, we develop python data access to web content through http request such as web services or web pages.

The story is as follows: You found something on the web that you'd like to interact with. 

* This could be data you'd like to have access to, 
* or some actions you'd like to perform -- such as search, posting an article, buying some bitcoin, etc.. 
* If you're really lucky, someone's already written a python layer to do what you want to do. 
* If you're just lucky, the resource comes with a clear interface definition that makes it 
easy for you to write your own python for. 
* If you're less lucky, you'll have to decipher some bad documentation of the API, 
or even write your own bots, crawlers and parsers to get what you want. 

We want to make that all easier for you.

What we'll focus on for now is the fundamental common aspect of making a python layer to the http requests. 

"But... the excellent [`requests` library](https://requests.readthedocs.io/en/master/) 
already provides the python wrapper to http!" you say. Yes, and we thank the `requests` developers for that. 
It is indeed an excellent package that we won't have to write now! 

We'd like to build from there, cover more annoying boilerplate, and get you closer, faster, 
to the functionality you actually need: 
Functions with the python types you're using in your code, 
that responds with python objects you can directly use in your code. 

The development of `requests` 
(including the [recommended add-ons](https://requests.readthedocs.io/en/master/community/recommended/)) 
could be said to be facing the metal (raw http mechanics) and building interfaces with humans in mind. 
By contrast, we want to face the human and build adapters to communicate with the metal. 
That is, in our case, the fact that http is under the hood shouldn't even be visible (unless it needs to).

It's in honor of the inspiration of "designing for humans" that we extend requests' tag-line, 
to "requests for humans".

# The approach

As always, we favor expressiveness, boilerplate minimization, separation of concerns, and a layered approach that 
incrementally transforms and enhance to get us from where we are to where we want to be.

So for py2request, where are we and where do we want to be?

**What we have**: We have some http accessible resources. For instance, a perfectly well structured API 
specification of a REST webservice, a very messy website, or anything in between.

**What we'd like**: A Python interface to these web stuff. 
That is, we want to talk python to the resources, and have it talk python back to us. 
Further, we want this conversation to be to the point; we don't want to have to say more than the exact necessary, 
and don't want responses containing anything but exactly what we want and how we want it. 
Finally, we'd like to get this with minimum effort -- letting default choices be made for us, but being able to make 
our own choices if we want.

Is that too much to ask?

In the layered approach we'll go from function specifications, to functions returning python 
Request objects, which we can then wrap further to create functions actually executing the request, 
getting back a Response object, and wrap further to get the final python output type.

So the objects in this pipeline are:
* Specification
* Request
* Response
* Final python object
