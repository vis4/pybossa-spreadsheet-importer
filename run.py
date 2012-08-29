#!/usr/bin/env python

import web
import pbclient
import requests
import re

web.config.debug = True

urls = (
    '/', 'index',
    '/submit', 'submit',
    '/status', 'status',
)

app = web.application(urls, globals())
render = web.template.render('templates/')

last_status = 'ready.'

class index:
    def GET(self):
        web.header('Content-type','text/html')
        web.header('Transfer-Encoding','chunked')
        return render.index()


class submit:
    def POST(self):
        global last_status
        data = web.input()
        last_status = '<p>Connecting to PyBossa <i class="loading"></i></p>'
        # check endpoint and api_key
        pbclient.set('endpoint', data.endpoint)
        pbclient.set('api_key', data.api_key)
        app = pbclient.find_app(short_name=data.appname)
        if len(app) == 0:
            last_status += '<p class="error" data-field="appname">PyBossa app not found.</p>'
        else:
            app = app[0]
            res = pbclient.update_app(app)
            if res == 403:
                last_status += '<p class="error" data-field="api_key">You\'re not allowed to edit that app. Double check your API key.</p>'
            else:
                last_status += '<p>Loading data from Google spreadsheet <i class="loading"></i></p>'
                url = 'http://spreadsheets.google.com/feeds/cells/%s/%s/public/basic?alt=json' % (data.spreadsheet, data.worksheet)
                r = requests.get(url)
                if r.status_code / 100 == 4:
                    last_status += '<p class="error" data-field="spreadsheet">The spreadsheet could not be found. Make sure that the key is right and that you properly shared the document (click on <i>File > Publish to the web</i>).</p>'
                else:
                    last_status += '<p>Parsing spreadsheet data <i class="loading"></i></p>'
                    tasks = parse_spreadsheet(r.json)
                    tmp = last_status
                    total = len(tasks)
                    completed = 0
                    for info in tasks:
                        info['n_answers'] = int(data.n_answers)
                        res = pbclient.create_task(app.id, info)
                        completed += 1
                        last_status = tmp + '<p>Uploading tasks to PyBossa (%d of %d)<i class="loading"></i></p>' % (completed, total)
                    last_status += '<p>finished.</p>'
        print ''


class status:
    def GET(self):
        return last_status


def parse_spreadsheet(data):
    # borrowed from https://github.com/misoproject/dataset/blob/master/src/parsers/google_spreadsheet.js#L126
    positionRegex = re.compile('([A-Z]+)(\d+)')
    columnPositions = dict()
    columnNames = []
    res = []
    for cell in data['feed']['entry']:
        content = cell['content']['$t']
        parts = positionRegex.match(cell['title']['$t'])
        column = parts.group(1)
        position = int(parts.group(2)) - 1
        # this is the first row, thus column names.
        if position == 0:
            # if we've already seen this column name, throw an exception
            if content in columnNames:
                raise Exception('Duplicate column names.')
            else:
                columnPositions[column] = len(columnPositions)
                columnNames.append(content)
        else:
            # find position
            if position > len(res):
                res.append(dict())
            res[position - 1][columnNames[columnPositions[column]]] = content
    return res

def test():
    import os.path
    import json
    if os.path.exists('cache'):
        parse_spreadsheet(json.loads(open('cache').read()))
    else:
        url = 'http://spreadsheets.google.com/feeds/cells/0AjrRp_WagR7RdFZwaDBLRjB0SF8xcEI0RGtQMHFuSXc/1/public/basic?alt=json'
        r = requests.get(url)
        open('cache', 'w').write(r.text)
        parse_spreadsheet(r.json)

if __name__ == "__main__":
    app.run()
    #test()
