from processing.gui.wrappers import WidgetWrapper
from qgis.PyQt.QtWidgets import QDateEdit
from qgis.PyQt.QtCore import Qt, QCoreApplication, QDate

from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterFolderDestination
from qgis.core import QgsProcessingParameterFile
from qgis.core import QgsProcessingParameterRasterDestination, QgsProcessingParameterRasterLayer
from qgis.core import QgsCoordinateReferenceSystem
from qgis.core import QgsProcessingParameterEnum
from qgis.core import QgsProcessingParameterString
from qgis.core import QgsRasterLayer
from PyQt5.QtCore import QDateTime, QDate
import processing
import pandas
import numpy
from datetime import datetime, timedelta
import time
import re
import os
import tempfile

from urllib.parse import urlparse
from osgeo import gdal


class Download_copernicus(QgsProcessingAlgorithm):

    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None):
        # pre-load
        self.services = []
        alg_params = {
            'URL': 'https://land.copernicus.vgt.vito.be/manifest/',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        output = processing.run('native:filedownloader', alg_params)
        print ("pre-load", output)
        dfs = pandas.read_html(output['OUTPUT'])
        df = dfs[0]
        for index,row in df.iterrows():
            if not pandas.isna(row[1]) and row[1] != 'Parent Directory':
                self.services.append(row[1][:-1])
            
        #print ("SERVICES", self.services)
        
        #self.addParameter(QgsProcessingParameterRasterLayer('source_file', 'source_file', defaultValue=None))
        
        self.addParameter(QgsProcessingParameterEnum('Product collection', 'Product collection', options=self.services, defaultValue=None))

        param = QgsProcessingParameterString('Select the day', 'Select the day')
        param.setMetadata({
            'widget_wrapper': {
                'class': DateTimeWidget}})

        self.addParameter(param)
        
        self.addParameter(QgsProcessingParameterFile('Download directory', 'Download directory', behavior=QgsProcessingParameterFile.Folder, optional=True, defaultValue=None))
        self.addParameter(QgsProcessingParameterRasterDestination('Download file', 'Download file', createByDefault=True, defaultValue=None))

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        #feedback = QgsProcessingMultiStepFeedback(2, model_feedback)
        results = {}
        outputs = {}

        download_service = self.services[parameters['Product collection']]
        
        #STEP1
        alg_params = {
            'URL': 'https://land.copernicus.vgt.vito.be/manifest/%s' % download_service,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        output = processing.run('native:filedownloader', alg_params)
        dfs = pandas.read_html(output['OUTPUT'])
        df = dfs[0]
        for index,row in df.iterrows():
            if not pandas.isna(row[1]) and row[1].startswith('manifest'):
                manifest_url = row[1]
        
        #STEP2
        url = 'https://land.copernicus.vgt.vito.be/manifest/%s/%s' % (download_service, manifest_url)
        alg_params = {
            'URL': url,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        output = processing.run('native:filedownloader', alg_params)
        log = []
        max_delta = timedelta.max.total_seconds()
        target = None
        td = datetime.strptime( parameters['Select the day'], '%Y-%m-%dT%H:%M:%S' )
        with open(output['OUTPUT'], 'r') as t:
            for line in t.readlines():
                r = re.findall(r"((\/)\d\d\d\d(\/)\d\d(\/)\d\d(\/))",line)
                match = r[0][0]
                ud = datetime.strptime(match, "/%Y/%m/%d/")
                log.append({
                    "url": line.replace("\n",''),
                    "date": ud
                })
                dd = td - ud
                if abs(dd.total_seconds()) < max_delta:
                    max_delta = abs(dd.total_seconds())
                    target = line.replace("\n",'')
                    
        #STEP3
        u = urlparse(target)
        filepath, filename = os.path.split(u.path)
        target_dir = self.parameterAsFile(parameters, 'Download directory', context).replace("/Download directory",'')
        
        #target_file = self.parameterAsFile(parameters, 'Download directory', context)
        #print ("target_file",target_file)
        
        #if not target_file:
        target_file = os.path.join(target_dir, filename)
        
        print ("target_dir",target_dir)
        alg_params = {
            'URL': target,
            'OUTPUT': target_file
        }
        print (alg_params)
        outputs['file'] = processing.run('native:filedownloader', alg_params, context=context, feedback=model_feedback, is_child_algorithm=True)
        input_nc_source = outputs['file']['OUTPUT']
        print ("NETCDF source",input_nc_source)
        nc_source = gdal.Open('NETCDF:"%s"' % input_nc_source)
        nc_info = gdal.Info(nc_source)
        nc_rex = re.compile('":.+SUBDATASET_1_DESC', re.MULTILINE|re.DOTALL)
        first_subds_match = nc_rex.search(nc_info)
        if first_subds_match:
            first_subds_name = first_subds_match.group(0).split("  ")[0][2:-1]
            print ("FIRST SUBDATASET NAME", first_subds_name)
            
            uri='NETCDF:"%s":%s' % (input_nc_source, first_subds_name)
        else:
            first_subds_name = ""
            uri=input_nc_source
        input_raster = QgsRasterLayer(uri,download_service)

        #print(input_raster.dataProvider().bandStatistics(1).minimumValue)
        
        output_tiff = target_file+".tif"
        
        '''
        translateoptions = gdal.TranslateOptions(gdal.ParseCommandLine("-if netCDF -of Gtiff"))
        try:
            res = gdal.Translate(output_raster, input_nc_source+":"+first_subds_name, options=translateoptions)
            return {'OUTPUT': output_raster, 'INPUT': input_nc_source+":"+first_subds_name, 'ERROR': ''}
        except Exception as e: 
            return {'OUTPUT': '', 'INPUT': input_nc_source+":"+first_subds_name, 'ERROR': e}
            
        '''
                
        # Xmin = -180 + ((1 / 112) / 2)
        # Xmax = 180 - ((1 / 112) / 2)
        # Ymax = 80 - ((1 / 112) / 2)
        # Ymin = -60 + ((1 / 112) / 2)

        # pixelX= 1./112.
        # pixelY= 1./112.

        # stats= input_raster.dataProvider().bandStatistics(1)

        # src_min= stats.minimumValue
        # src_max= stats.maximumValue
        # dst_min= stats.minimumValue
        # dst_max= stats.maximumValue

        # print (src_min, src_max, dst_min, dst_max)


        tra_extra = "-of Gtiff -co COMPRESS=DEFLATE -co PREDICTOR=2 -co ZLEVEL=9 "
        #tra_extra += " -projwin " + str(Xmin) + " " + str(Ymax) + " " + str(Xmax) + " " + str(Ymin)
        #tra_extra += " -r average -tr " + str(pixelX) + " " + str(pixelY)
        #tra_extra += " -scale " + str(src_min) + " " + str(src_max) + " " + str(dst_min) + " " + str(dst_max)


        alg_params = {
            'INPUT': input_raster,
            'EXTRA': tra_extra,
            'OUTPUT': output_tiff
        }
        print ("params",alg_params)
        outputs['translate'] = processing.run('gdal:translate', alg_params, context=context, feedback=model_feedback, is_child_algorithm=True)
        return {'Download file': outputs['translate']['OUTPUT'],  "RESOURCE": target}
    
    


    def name(self):
        return 'Download Copernicus Global Land'

    def displayName(self):
        return 'Download Copernicus Global Land'

    def group(self):
        return 'Copernicus Global Land Tools'

    def groupId(self):
        return 'Copernicus Global Land Tools'

    def shortHelpString(self):
        """
        Returns a localised short helper string for the algorithm. This string
        should provide a basic description about what the algorithm does and the
        parameters and outputs associated with it..
        """
        return "This algorithm allows to download Copernicus Global Land products and converts the native Netcdf files into geotiff." \
               "Select the product collection to downlad and the day. The algorithm will download the product with the closest date. " \
               "Download directory is the directory in wich the product will be downloaded and converted to geotiff. " \
               "Download file: it is an addionatal parameter, leave empty"

    def createInstance(self):
        return Download_copernicus()

class DateTimeWidget(WidgetWrapper):
    """
    QDateTimeEdit widget with calendar pop up
    """

    def createWidget(self):
        self._combo = QDateEdit()
        self._combo.setCalendarPopup(True)

        today = QDate.currentDate()
        self._combo.setDate(today)

        return self._combo

    def value(self):
        date_chosen = self._combo.dateTime()
        return date_chosen.toString(Qt.ISODate)
