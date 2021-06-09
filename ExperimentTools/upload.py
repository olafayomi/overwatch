import gspread
import csv
import sys
import argparse
import glob
import pathlib
from oauth2client.service_account import ServiceAccountCredentials

scope = ["https://spreadsheets.google.com/feeds",
         'https://www.googleapis.com/auth/spreadsheets',
         "https://www.googleapis.com/auth/drive.file",
         "https://www.googleapis.com/auth/drive"]
csv_dir = '/home/ubuntu/CSV-DELAYS/'

#credentials = ServiceAccountCredentials.from_json_keyfile_name('phd-research-par-delay-data.json',
#        scope)
#client = gspread.authorize(credentials)
#
#spreadsheet = client.open('CSV-to-Google-Sheet')
#sheetName = '20210527-2'
#spreadsheet.add_worksheet(title=sheetName, rows="10000", cols="14")
#spreadsheet.values_update(sheetName,
#        params={'valueInputOption': 'USER_ENTERED'},
#        body={'values': list(csv.reader(open('/home/ubuntu/CSV-DELAYS/20210527-2.csv')))})


if __name__ == "__main__":
    argParser = argparse.ArgumentParser(
            description='Upload delay CSV files to Google Sheets',
            usage='%(prog)s [--date 20210604 --spreadsheet experiment-2021064]')
    argParser.add_argument('--date', dest='date_str', 
                           help='Date string in CSV filenames',
                           default=None)
    argParser.add_argument('--spreadsheet', dest='sheetname',
                           help='Name of the Google spreadsheet to upload files',
                           default=None)
    argParser.add_argument('--runs', dest='runs',
                           help='Number of experiment run', type=int,
                           default=10)
    args = argParser.parse_args()

    if args.date_str is None:
        print("Date string for CSV filenames not provided!!!")
        sys.exit(-1) 

    if args.sheetname is None:
        print("Google sheet name not provided!!!")
        sys.exit(-1)

    #Authenticate and check if Google Sheet exists
    credentials = ServiceAccountCredentials.from_json_keyfile_name('phd-research-par-delay-data.json',
            scope)
    gclient = gspread.authorize(credentials) 
    try:
        sheet = gclient.open(args.sheetname)
    except gspread.SpreadsheetNotFound:
        sheet = gclient.create(args.sheetname) 
    
    sheet.share('oof1@students.waikato.ac.nz', perm_type='user', role='writer')
    sheet.share('olafayomi@gmail.com', perm_type='user', role='writer')


    for i in range(1, args.runs+1):
        path_pattern = csv_dir+'*'+args.date_str+'-'+str(i)+'*' 
        path = glob.glob(path_pattern) 

        if not path:
            print("CSV file does exist for experiment run %s on %s" %(i, args.date_str))
            continue

        for csvfile in path:
            csvfilepath = pathlib.Path(csvfile) 

            if not csvfilepath.is_file():
                print("%s does not exist!!!!" %(csvfilepath))
                continue

            worksheetName = csvfilepath.stem
            try:
                wsheet = sheet.add_worksheet(title=worksheetName, rows="1000", cols="14")
            except gspread.exceptions.APIError:
                sheet.del_worksheet(wsheet.id)
                wsheet = sheet.add_worksheet(title=worksheetName, rows="1000", cols="14")
                
            sheet.values_update(worksheetName,
                    params={'valueInputOption': 'USER_ENTERED'},
                    body={'values': list(csv.reader(open(csvfile)))})
            print("Uploaded %s to %s" %(worksheetName,args.sheetname))
    print("Done!!!")


        



