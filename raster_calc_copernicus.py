from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterNumber
from qgis.core import QgsProcessingParameterString
from qgis.core import QgsProcessingParameterRasterLayer
from qgis.core import QgsProcessingParameterRasterDestination
from qgis.core import QgsProcessingParameterVectorLayer
from qgis.core import QgsProcessingParameterMultipleLayers
from qgis.core import QgsRasterLayer
from qgis.core import QgsProject, QgsCoordinateTransformContext
import processing
import os
import tempfile

from qgis.analysis import QgsRasterCalculatorEntry, QgsRasterCalculator


class CopernicusRasterCalculator(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterMultipleLayers('LAYERS', 'LAYERS', layerType=QgsProcessing.TypeRaster, defaultValue=None))
        self.addParameter(QgsProcessingParameterString('FORMULA', 'FORMULA', defaultValue=None))
        self.addParameter(QgsProcessingParameterRasterLayer('SAMPLE', 'SAMPLE', defaultValue=None))
        self.addParameter(QgsProcessingParameterRasterDestination('OUTPUT', 'OUTPUT', createByDefault=True, defaultValue=None))

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model

        sample_raster = self.parameterAsRasterLayer(parameters, 'SAMPLE', context)
        layers = self.parameterAsLayerList(parameters, 'LAYERS', context)
        
        letter_order = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        
        raster_entries = []
        for idx,raster_layer in enumerate(layers):
            for band in range(1,raster_layer.bandCount()+1):
                raster_entry = QgsRasterCalculatorEntry()
                raster_entry.raster = raster_layer
                raster_entry.bandNumber = band
                raster_entry.ref = "{}@{}".format(letter_order[idx],band)
                print ( raster_entry.ref )
                raster_entries.append(raster_entry)
        
        #output_raster_path = os.path.join(tempfile.mkdtemp(),"OUTPUT.tif")
        #output_raster_path = parameters['OUTPUT']
        output_raster_path = self.parameterAsOutputLayer(parameters, 'OUTPUT', context)

        
        tc = QgsCoordinateTransformContext(QgsProject.instance().transformContext())

        print('extent', sample_raster.extent())
        print('widht', sample_raster.width())
        print('height', sample_raster.height())
        print(type(sample_raster.extent()))

        
        calc = QgsRasterCalculator( parameters['FORMULA'], output_raster_path, 'GTiff', sample_raster.extent(), sample_raster.width(), sample_raster.height(), raster_entries, tc  )

        print ("COPERNICUSRASTERCALC",parameters['FORMULA'], output_raster_path, 'GTiff', sample_raster.extent(), sample_raster.width(), sample_raster.height(), raster_entries, tc  )
        #return results
        
        if calc.processCalculation() == 0:
            rasterCalcError = "No error"
            results = {'ERROR': '','OUTPUT': output_raster_path}
        else:
            rasterCalcError = calc.lastError()
            results = {'OUTPUT': '', 'ERROR': rasterCalcError}

        return results

    def name(self):
        return 'copernicusrastercalculator'

    def displayName(self):
        return 'Copernicus raster calculator'

    def group(self):
        return 'Copernicus Global Land Tools'

    def groupId(self):
        return 'Copernicus Global Land Tools'

    def createInstance(self):
        return CopernicusRasterCalculator()
