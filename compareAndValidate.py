import urllib2, os, zipfile, tempfile, sys
import getopt,difflib, optparse
import os.path, subprocess
from filecmp import dircmp
import smtplib
from email.MIMEMultipart import MIMEMultipart
from email.MIMEBase import MIMEBase
from email import Encoders
from email.MIMEText import MIMEText
from email.Utils import COMMASPACE, formatdate
import shutil
import logging
logger = logging.getLogger(__name__)

'''
The purpose of this script is to download XSD artifacts from NEXUS which are LITP artifacts
Current Version and Previous Versions of the XSD's are fetched and then compared
If there is a difference then a notification of the diff is email
'''

def getArguments(argv):
    '''
    The getArguments function takes user input parameters declared as arguments from the command line
    '''
    currentVersion = ""
    previousVersion = ""
    email = ""
    try:
        opts,args = getopt.getopt(argv, "c:p:e:h", ["currentVersion=", "previousVersion=","email=", "help="])
    except Exception as e:
        logger.error("Issue with script parameters: " +str(e))
        sys.exit(1)
    try:
        for opt, arg in opts:
            if opt in ("-c", "--currentVersion"):
                currentVersion = arg
            if opt in ("-p", "--previousVersion"):
                previousVersion = arg
            if opt in ("-e", "--email"):
                email = arg
            if opt in ("-h", "--help"):
                help = arg
                logger.info("This Script Gets the Current and Previous versions of LITP XSD's from nexus, compares, validates and notifies")
                sys.exit(1)
        if currentVersion and previousVersion and email:
            return currentVersion, previousVersion, email
        else:
            logger.info("Please Ensure that the script parameters --currentVersion, --previousVersion, --email are declared")
            sys.exit(1)
    except Exception as e:
        logger.error("Issue with script parameters: " +str(e))
        return 1

def downloadFile(source, destination):
    '''
    The downloadFile function takes the artfcats down from Nexus and stores them locally
    '''
    try:
        file_name = source.split('/')[-1]
        try:
            url = urllib2.urlopen(source)
        except Exception as e:
            logger.error("Issue url2lib plugin flow: ")
            return 1
        try:
            file = open(destination + "/" + file_name, 'wb')
        except Exception as e:
            logger.error("Issue with opening destination with file name: " +str(file_name))
            return 1
        meta = url.info()
        fileSize = int(meta.getheaders("Content-Length")[0])
        fileSizeDownloaded = 0
        blockSize = 8388608
        while True:
            buffer = url.read(blockSize)
            if not buffer:
                break
            fileSizeDownloaded += len(buffer)
            file.write(buffer)
            status = r"%10d  [%3.2f%%]" % (fileSizeDownloaded, fileSizeDownloaded * 100. / fileSize)
            status = status + chr(8)*(len(status)+1)
        file.close()
    except Exception as e:
        logger.error("Issue downlaoding file from Nexus: " +str(e))
        return 1

def downloadXSD(completeArtifactURL,tmpArea):
    '''
    Class used to Download the XSD's from the Nexus Repositiories

    Parameters taken in tmparea to place the jar in and the mapping file used to tell
    which release is for which sprint
    '''
    artifact = completeArtifactURL.split('/')[-1]
    logger.info("Downloading Artifact: " +str(artifact) + " from Nexus")
    try:
        downloadFile(completeArtifactURL,tmpArea)
        logger.info("Successfully downloaded Artifact: " +str(artifact) + " from Nexus")
        return artifact
    except Exception as e:
        logger.error("Could not download " + artifact + " due to error " +str(e))
        return 1 

def extractJar(tmpArea,artifact):
    '''
    Class used to extract a given jar file

    Parameters given area where the jar file is stored and the jar file name
    '''
    try:
        logger.info("Extracting Artifact: " + str(artifact))
        extractJar = os.path.join(tmpArea,artifact)
        zip_file = zipfile.ZipFile(extractJar, 'r')
        for files in zip_file.namelist():
            zip_file.extract(files, tmpArea)
        zip_file.close()
    except Exception as e:
        logger.error("There was an issue un-jar'n the artifact locally: " +str(e))
        return 1


def compareAndBuildReport(dir1,dir2):
    '''
    The compareAndBuildReport function compares the current xsd dir and previous and build report if there is a diff
    '''
    try:
        reportFile = ("/tmp/compareXSDReport.txt")
        command = ('sdiff -s ' + str(dir1) + " " + str(dir2) + " > " + str(reportFile))
        process = subprocess.Popen(command, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        process.communicate()
        logger.info("Built up report file without issue")
        return reportFile
    except Exception as e:
        logger.error("Issue with building up diff report file: " +str(e))
        return 1

def print_diff_files(dcmp):
    '''
    The print_diff_files function finds if there is a difference in the current and previous versions of XSD's
    '''
    try:
        for name in dcmp.diff_files:
            logger.info("diff_file %s found in %s and %s" % (name, dcmp.left,
                  dcmp.right))
            return True
        for sub_dcmp in dcmp.subdirs.values():
            print_diff_files(sub_dcmp)
            return False
    except Exception as e:
        logger.error("There was an issue determining if there is a difference between versions: " +str(e))
        return 1

def sendNotification(reportFile, email):
    '''
    The sendNotification function sends a notification mail if there is a difference in the XSD's
    '''
    try:
        subject = "Alert: There has been an LITP XSD update"
        msg = MIMEMultipart()
        sender = "PDLRENEWAL@ex1.eemea.ericsson.se"
        msg['Subject'] = subject 
        msg['From'] = sender 
        email = COMMASPACE.join([email])
        msg['To'] = email
        msg['Date'] = formatdate(localtime=True)

        body = ("Hi There \nThere has been an LITP XSD update, Please see attached file. \nRegards \nCI Execution Team") 
        msg.attach(MIMEText(body))

        part = MIMEBase('application', "octet-stream")
        part.set_payload(open(reportFile, "rb").read())
        Encoders.encode_base64(part)

        part.add_header('Content-Disposition', 'attachment; filename="compareXSDReport.txt"')

        msg.attach(part)
        
        email = email.split(",")
        for mail in email:
            server = smtplib.SMTP('localhost')
            server.sendmail(sender, mail, msg.as_string()) 
            logger.info("Notification send wihout issue to: " +str(mail))
    except Exception as e:
        logger.error("Issue sending notification: " +str(e))
        return 1

def cleanup(tmpAreaList,report):
    '''
    The cleanup functions is used to clean up created tmp area's and reports
    '''
    for item in tmpAreaList:
        try:
            if (os.path.exists(item)):
                shutil.rmtree(item)
                logger.info("Successfully Removed the " + str(item))
        except Exception as e:
            logger.error("There was a problem removing the tmpArea "  + str(e))
            return 1
    if report != None:
        try:
            os.remove(report)
            logger.info("Report deleted with success: " +str(report))
        except Exception as e:
            logger.error("Issue deleting report: " +str(e))
            return 1
    return 0

def getAndCompareXSDs():
    '''
    The getAndCompareXSDs functions is the main function which calls:
    Download XSD's functiom
    Unjar's XSD's to tmp areas
    Compares
    Sends Notification
    Cleans Up
    '''
    currentVersion, previousVersion, email = getArguments(sys.argv[1:])
    artifactList = (currentVersion, previousVersion)
    dirList = []
    tmpAreaList = []
    try:
        for version in artifactList:
            completeArtifactURL = ("https://arm1s11-eiffel004.eiffel.gic.ericsson.se:8443/nexus/content/repositories/releases/com/ericsson/nms/LitpXSD/" + str(version) + "/LitpXSD-" + str(version) + ".jar")
            tmpArea = tempfile.mkdtemp()
            tmpAreaList.append(tmpArea)
            #dirList.append(tmpArea + "/opt/ericsson/nms/litp/share/xsd/")
            dirList.append(tmpArea + "/")
            artifact = downloadXSD(completeArtifactURL,tmpArea)
            extractJar(tmpArea,artifact)
            logger.info("Successfully downloaded artifacts from Nexus and extracted XSD's locally")
    except Exception as e:
        logger.error("Issue Getting artifacts and extracting the XSD's locally: " +str(e))
        return 1
    try:
        dcmp = dircmp(dirList[0], dirList[1])
        status = print_diff_files(dcmp)
        logger.info("Successfully compared current Version of XSD's to previous Version")
    except Exception as e:
        logger.error("Issue with commparision between current Version of XSD's to previous Version: " +str(e))
        return 1
    report = None
    if status == True:
        try:
            report = compareAndBuildReport(dirList[0], dirList[1])
            logger.info("Ran through compareAndBuildReport with success")
        except Exception as e:
            logger.error("Issue running through compareAndBuildReport: " +str(e))
            return 1
        try:
            sendNotification(report,email)
            logger.info("Sent Notification with Success")
        except Exception as e:
            logger.error("Issue send notification: " + str(e))
            return 1
    else:
        logger.info("There is no difference in XSD's therefore job is finished and no notification will be sent")

    try:
        cleanup(tmpAreaList,report)
        logger.info("Cleaned up tmp areas with success")
    except Exception as e:
        logger.error("Issue doing cleanup on tmp area created: " +str(e))
        return 1

if __name__ == "__main__":
    try:
        getAndCompareXSDs()
        logger.info("Successfully Ran through all Tasks")
    except Exception as e:
        logger.error("Issue running through tasks: " +str(e))
