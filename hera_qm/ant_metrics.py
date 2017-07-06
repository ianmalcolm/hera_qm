import numpy as np
import matplotlib.pyplot as plt
import aipy as a 
from copy import deepcopy
from pyuvdata import UVData
import json


#######################################################################
#Low level functionality that is potentially reusable
#######################################################################


def per_antenna_modified_z_scores(metric):
    '''For a given metric, stored as a (ant,antpol) dictonary, computes the per-pol modified z-score 
    for each antenna, which is the metrics, minus the median, divided by the median absolute deviation.'''
    zscores = {}    
    antpols = set([key[1] for key in metric.keys()])
    for antpol in antpols:            
        values = np.array([val for key,val in metric.items() if key[1]==antpol])
        median = np.nanmedian(values)
        medAbsDev = np.nanmedian(np.abs(values - median))
        for key,val in metric.items(): 
            if key[1]==antpol:
                zscores[key] = 0.6745*(val - median) / medAbsDev 
                #this factor makes it comparable to a standard z-score for gaussian data
    return zscores

def mean_Vij_metrics(data, pols, antpols, ants, bls, xants=[], rawMetric=False):
    '''Calculates how an antennas's average |Vij| deviates from others.

    Arguments:
    data -- data for all polarizations in a format that can support data.get_data(i,j,pol)
    pols -- List of visibility polarizations (e.g. ['xx','xy','yx','yy']).
    antpols -- List of antenna polarizations (e.g. ['x', 'y'])
    ants -- List of all antenna indices.
    bls -- List of tuples of antenna pairs.
    xants -- list of antennas in the (ant,antpol) format that should be ignored.
    rawMetric -- return the raw mean Vij metric instead of the modified z-score

    Returns:
    meanMetrics -- a dictionary indexed by (ant,antpol) of the modified z-score of the mean of the 
    absolute value of all visibilities associated with an antenna. Very small or very large numbers 
    are probably bad antennas.
    '''
    
    absVijMean = {(ant,antpol):0.0 for ant in ants for antpol in antpols if (ant,antpol) not in xants}
    visCounts = deepcopy(absVijMean)
    for (i,j) in bls:
        if i != j:
            for pol in pols:
                for ant, antpol in zip((i,j), pol):
                    if (ant,antpol) not in xants:
                        absVijMean[(ant,antpol)] += np.abs(data.get_data(i,j,pol))
                        visCounts[(ant,antpol)] += 1
    timeFreqMeans = {key: np.nanmean(absVijMean[key] / visCounts[key]) for key in absVijMean.keys()}

    if rawMetric: 
        return timeFreqMeans
    else: 
        return per_antenna_modified_z_scores(timeFreqMeans)

def red_corr_metrics(data, pols, antpols, ants, reds, xants=[], rawMetric=False, crossPol=False):
    '''Calculates the extent to which baselines involving an antenna don't correlated
    with others they are nominmally redundant with.

    Arguments:
    data -- data for all polarizations in a format that can support data.get_data(i,j,pol)
    pols -- List of visibility polarizations (e.g. ['xx','xy','yx','yy']).
    antpols -- List of antenna polarizations (e.g. ['x', 'y'])
    ants -- List of all antenna indices.
    reds -- List of lists of tuples of antenna numbers that make up redundant baseline groups.
    xants -- list of antennas in the (ant,antpol) format that should be ignored.
    rawMetric -- return the raw power correlations instead of the modified z-score
    crossPol -- return results only when the two visibility polarizations differ by a single flip

    Returns:
    powerRedMetric -- a dictionary indexed by (ant,antpol) of the modified z-scores of the mean 
    power correlations inside redundant baseline groups that the antenna participates in.
    Very small numbers are probably bad antennas.
    '''

    #Precompute auto-powers to save time
    autoPower ={} 
    for pol in pols:
        for bls in reds:
            for (i,j) in bls:
                autoPower[i,j,pol] = np.median(np.sum(np.abs(data.get_data(i,j,pol))**2, axis=0))

    #Compute power correlations and assign them to each antenna
    antCorrs = {(ant,antpol):0.0 for ant in ants for antpol in antpols if (ant,antpol) not in xants}
    antCounts = deepcopy(antCorrs)
    for pol0 in pols:
        for pol1 in pols:
            iscrossed_i = (pol0[0] != pol1[0])
            iscrossed_j = (pol0[1] != pol1[1])
            onlyOnePolCrossed = (iscrossed_i ^ iscrossed_j)
            #This function can instead record correlations for antennas whose counterpart are pol-swapped
            if (not crossPol and (pol0 is pol1)) or (crossPol and onlyOnePolCrossed):
                for bls in reds:
                    for n,(ant0_i,ant0_j) in enumerate(bls):
                        data0 = data.get_data(ant0_i,ant0_j,pol0)
                        for (ant1_i,ant1_j) in bls[n+1:]:
                            data1 = data.get_data(ant1_i,ant1_j,pol1)
                            corr = np.median(np.abs(np.sum(data0*data1.conj(), axis=0)))
                            corr /= np.sqrt(autoPower[ant0_i,ant0_j,pol0] 
                                            * autoPower[ant1_i,ant1_j,pol1])
                            antsInvolved = [(ant0_i,pol0[0]), (ant0_j,pol0[1]), 
                                            (ant1_i,pol1[0]), (ant1_j,pol1[1])]
                            if not np.any([(ant,antpol) in xants for ant,antpol in antsInvolved]):
                                #Only record the crossed antenna if i or j is crossed
                                if crossPol and iscrossed_i:
                                    antsInvolved = [(ant0_i,pol0[0]), (ant1_i,pol1[0])]
                                elif crossPol and iscrossed_j:
                                    antsInvolved = [(ant0_j,pol0[1]), (ant1_j,pol1[1])]
                                for ant,antpol in antsInvolved:
                                    antCorrs[(ant,antpol)] += corr
                                    antCounts[(ant,antpol)] += 1   

    #Compute average and return
    for key,count in antCounts.items():
        if count > 0: antCorrs[key] /= count
    if rawMetric:
        return antCorrs
    else:
        return per_antenna_modified_z_scores(antCorrs)


def exclude_partially_excluded_ants(antpols, xants):
    '''Takes a list of excluded antennas and adds on all polarizations of those antennas.'''
    xantSet = set(xants)
    for xant in xants:
        for antpol in antpols:
            xantSet.add((xant[0],antpol))
    return list(xantSet)


def antpol_metric_sum_ratio(ants, antpols, crossMetrics, sameMetrics, xants=[]):
    '''Takes the ratio of two antenna metrics, summed over both polarizations, and creates a new
    antenna metric with the same value in both polarizations for each antenna.'''
    crossPolRatio = {}
    for ant in ants: 
        if (ant,antpols[0]) not in xants:
            crossSum = np.sum([crossMetrics[(ant,antpol)] for antpol in antpols])
            sameSum = np.sum([sameMetrics[(ant,antpol)] for antpol in antpols])
            for antpol in antpols: 
                crossPolRatio[(ant,antpol)] = crossSum/sameSum
    return crossPolRatio


def mean_Vij_cross_pol_metrics(data, pols, antpols, ants, bls, xants=[], rawMetric=False):
    '''Find which antennas are outliers based on the ratio of mean cross-pol visibilities to 
    mean same-pol visibilities: (Vxy+Vyx)/(Vxx+Vyy).

    Arguments:
    data -- data for all polarizations in a format that can support data.get_data(i,j,pol)
    pols -- List of visibility polarizations (e.g. ['xx','xy','yx','yy']).
    antpols -- List of antenna polarizations (e.g. ['x', 'y'])
    ants -- List of all antenna indices.
    bls -- List of tuples of antenna pairs.
    xants -- list of antennas in the (ant,antpol) format that should be ignored. If, e.g., (81,'y')
            is excluded, (81,'x') cannot be identified as cross-polarized and will be excluded.
    rawMetric -- return the raw power ratio instead of the modified z-score

    Returns:
    mean_Vij_cross_pol_metrics -- a dictionary indexed by (ant,antpol) of the modified z-scores of the  
            ratio of mean visibilities, (Vxy+Vyx)/(Vxx+Vyy). Results duplicated in both antpols. 
            Very large values are probably cross-polarized.
    '''

    # Compute metrics and cross pols only and and same pols only
    samePols = [pol for pol in pols if pol[0] == pol[1]]
    crossPols = [pol for pol in pols if pol[0] != pol[1]]
    full_xants = exclude_partially_excluded_ants(antpols, xants)
    meanVijMetricsSame = mean_Vij_metrics(data, samePols, antpols, ants, bls, xants=full_xants, rawMetric=True)
    meanVijMetricsCross = mean_Vij_metrics(data, crossPols, antpols, ants, bls, xants=full_xants, rawMetric=True)

    # Compute the ratio of the cross/same metrics, saving the same value in each antpol
    crossPolRatio = antpol_metric_sum_ratio(ants, antpols, meanVijMetricsCross, meanVijMetricsSame, xants=full_xants)
    if rawMetric:
        return crossPolRatio
    else:
        return per_antenna_modified_z_scores(crossPolRatio)

def red_corr_cross_pol_metrics(data, pols, antpols, ants, reds, xants=[], rawMetric=False):
    '''Find which antennas are part of visibilities that are significantly better correlated with 
    polarization-flipped visibilities in a redundant group. Returns the modified z-score.

    Arguments:
    data -- data for all polarizations in a format that can support data.get_data(i,j,pol)
    pols -- List of visibility polarizations (e.g. ['xx','xy','yx','yy']).
    antpols -- List of antenna polarizations (e.g. ['x', 'y'])
    ants -- List of all antenna indices.
    reds -- List of lists of tuples of antenna numbers that make up redundant baseline groups.
    xants -- list of antennas in the (ant,antpol) format that should be ignored. If, e.g., (81,'y')
            is excluded, (81,'x') cannot be identified as cross-polarized and will be excluded.
    rawMetric -- return the raw correlation ratio instead of the modified z-score

    Returns:
    redCorrCrossPolMetrics -- a dictionary indexed by (ant,antpol) of the modified z-scores of the 
            mean correlation ratio between redundant visibilities and singlely-polarization flipped 
            ones. Very large values are probably cross-polarized.
    '''

    # Compute metrics for singly flipped pols and just same pols
    full_xants = exclude_partially_excluded_ants(antpols, xants)
    samePols = [pol for pol in pols if pol[0] == pol[1]]
    redCorrMetricsSame = red_corr_metrics(data, samePols, antpols, ants, reds, xants=full_xants, rawMetric=True)
    redCorrMetricsCross = red_corr_metrics(data, pols, antpols, ants, reds, xants=full_xants, rawMetric=True, crossPol=True)

    # Compute the ratio of the cross/same metrics, saving the same value in each antpol
    crossPolRatio = antpol_metric_sum_ratio(ants, antpols, redCorrMetricsCross, redCorrMetricsSame, xants=full_xants)
    if rawMetric:
        return crossPolRatio
    else:
        return per_antenna_modified_z_scores(crossPolRatio)

def average_abs_metrics(metrics1, metrics2):
    '''Averages the absolute value of two metrics together.'''
    
    if set(metrics1.keys()) != set(metrics2.keys()):
        raise KeyError('Metrics being averaged have differnt (ant,antpol) keys.')
    return {key: np.abs(metrics1[key]/2) + np.abs(metrics2[key]/2) for key in metrics1.keys()}

def load_antenna_metrics(metricsJSONFile):
    '''Loads all cut decisions and meta-metrics from a JSON into python dictionary.'''
    
    with open(metricsJSONFile,'r') as infile:
        jsonMetrics = json.load(infile)
    return {key: eval(str(val)) for key,val in jsonMetrics.items()}

def plot_metric(metrics, ants=None, antpols=None, title='', ylabel='Modified z-Score', xlabel=''):
    '''Helper function for quickly plotting an individual antenna metric.'''

    if ants is None:
        ants = list(set([key[0] for key in metrics.keys()]))
    if antpols is None:
        antpols = list(set([key[1] for key in metrics.keys()]))
    
    for antpol in antpols:
        for i,ant in enumerate(ants):
            metric = 0
            if metrics.has_key((ant,antpol)):
                metric = metrics[(ant,antpol)]
            plt.plot(i,metric,'.')
            plt.annotate(str(ant)+antpol,xy=(i,metrics[(ant,antpol)]))
        plt.gca().set_prop_cycle(None)
    plt.title(title)
    plt.ylabel(ylabel)
    plt.xlabel(xlabel)



#######################################################################
#High level functionality for HERA
#######################################################################


class Antenna_Metrics():
    '''Object for holding relevant visibility data and metadata with interfaces to four 
    antenna metrics (two for identifying dead antennas, two for identifying cross-polarized ones), 
    an iterative method for identifying one bad antenna at a time while keeping track of all 
    metrics, and for writing metrics to a JSON.'''
    
    def __init__(self, dataFileList, reds, fileformat='miriad'):
        '''Arguments:
        dataFileList -- List of data filenames for the different polarizations
        reds -- List of lists of tuples of antenna numbers that make up redundant baseline groups
        format -- default miriad. Otheqr options: uvfits
        '''
        
        self.data = UVData()
        if fileformat is 'miriad':
            self.data.read_miriad(dataFileList)
        elif fileformat is 'uvfits':
            self.data.read_uvfits(dataFileList)
        else:
            raise ValueError('Unrecognized file format' + str(fileformat))
        self.ants = self.data.get_ants()
        self.pols = [pol.lower() for pol in self.data.get_pols()]
        self.antpols = [antpol.lower() for antpol in self.data.get_feedpols()]
        self.bls = list(set([(i,j) for (i,j,pol) in self.data.get_antpairpols()]))
        self.reds = reds

        # For using data containers until pyuvdata gets faster
        # from hera_cal import firstcal
        # from hera_qm.datacontainer import DataContainer
        # self.uvdata = self.data
        # datapack, flagspack = firstcal.UVData_to_dict([self.uvdata])
        # self.data = DataContainer(datapack)

        if len(self.antpols) is not 2 or len(self.pols) is not 4:
            raise ValueError('Missing polarization information. pols =' + str(self.pols) + ' and antpols = ' + str(self.antpols))

    def mean_Vij_metrics(self, pols=None, xants=[], rawMetric=False):
        '''Local wrapper for mean_Vij_metrics in hera_qm.ant_metrics module.'''

        if pols is None:
            pols = self.pols
        return mean_Vij_metrics(self.data, pols, self.antpols, self.ants, self.bls, xants=xants, rawMetric=rawMetric)


    def red_corr_metrics(self, pols=None, xants=[], rawMetric=False, crossPol=False):
        '''Local wrapper for red_corr_metrics in hera_qm.ant_metrics module.'''

        if pols is None:
            pols = self.pols
        return red_corr_metrics(self.data, pols, self.antpols, self.ants, self.reds, xants=xants, rawMetric=rawMetric, crossPol=crossPol)

    def mean_Vij_cross_pol_metrics(self, xants=[], rawMetric=False):
        '''Local wrapper for mean_Vij_cross_pol_metrics in hera_qm.ant_metrics module.'''
        
        return mean_Vij_cross_pol_metrics(self.data, self.pols, self.antpols, self.ants, self.bls, xants=xants, rawMetric=rawMetric)


    def red_corr_cross_pol_metrics(self, xants=[], rawMetric=False):
        '''Local wrapper for red_corr_cross_pol_metrics in hera_qm.ant_metrics module.'''

        return red_corr_cross_pol_metrics(self.data, self.pols, self.antpols, self.ants, self.reds, xants=xants, rawMetric=False)
    
    def _run_all_metrics(self):
        '''Designed to be run as part of AntennaMetrics.iterative_antenna_metrics_and_flagging().'''
        
        #Compute all raw metrics
        meanVij = self.mean_Vij_metrics(xants=self.xants, rawMetric=True)
        redCorr = self.red_corr_metrics(pols=['xx','yy'], xants=self.xants, rawMetric=True)
        meanVijXPol = self.mean_Vij_cross_pol_metrics(xants=self.xants, rawMetric=True)
        redCorrXPol = self.red_corr_cross_pol_metrics(xants=self.xants, rawMetric=True)   
        
        #Save all metrics and zscores
        metrics, modzScores = {}, {}
        for metName in ['meanVij','redCorr','meanVijXPol','redCorrXPol']:
            metric = eval(metName)
            metrics[metName] = metric
            modz = per_antenna_modified_z_scores(metric)
            modzScores[metName] = modz
            for key in metric.keys():
                if self.finalMetrics.has_key(metName):
                    self.finalMetrics[metName][key] = metric[key]
                    self.finalModzScores[metName][key] = modz[key]
                else:
                    self.finalMetrics[metName] = {key: metric[key]}
                    self.finalModzScores[metName] = {key: modz[key]}
        self.allMetrics.append(metrics)
        self.allModzScores.append(modzScores)        
    
    def iterative_antenna_metrics_and_flagging(self, crossCut=5, deadCut=5, verbose=False):
        '''Runs all four metrics (two for dead antennas two for cross-polarized antennas) and saves
        the results internally to this this antenna metrics object. 
        
        Arguments:
        crossCut -- Modified z-score cut for most cross-polarized antenna. Default 5 "sigmas".
        deadCut -- Modified z-score cut for most likely dead antenna. Default 5 "sigmas".
        '''
        
        #Summary statistics
        self.xants, self.crossedAntsRemoved, self.deadAntsRemoved = [], [], []
        self.removalIter = {}
        self.allMetrics, self.allModzScores = [], []
        self.finalMetrics, self.finalModzScores = {}, {}
        self.crossCut, self.deadCut = crossCut, deadCut
        
        #Loop over 
        for n in range(len(self.antpols)*len(self.ants)):
            self._run_all_metrics()
            
            # Mostly likely dead antenna
            deadMetrics = average_abs_metrics(self.allModzScores[-1]['meanVij'], 
                                              self.allModzScores[-1]['redCorr'])
            worstDeadAnt = max(deadMetrics, key=deadMetrics.get)
            worstDeadCutRatio = np.abs(deadMetrics[worstDeadAnt])/deadCut

            # Most likely cross-polarized antenna 
            crossMetrics = average_abs_metrics(self.allModzScores[-1]['meanVijXPol'],
                                               self.allModzScores[-1]['redCorrXPol'])
            worstCrossAnt = max(crossMetrics, key=crossMetrics.get)
            worstCrossCutRatio = np.abs(crossMetrics[worstCrossAnt])/crossCut

            # Find the single worst antenna, remove it, log it, and run again
            if worstCrossCutRatio >= worstDeadCutRatio and worstCrossCutRatio >= 1.0:
                for antpol in self.antpols:
                    self.xants.append((worstCrossAnt[0],antpol))
                    self.crossedAntsRemoved.append((worstCrossAnt[0],antpol))
                    self.removalIter[(worstCrossAnt[0],antpol)] = n
                    if verbose:
                        print 'On iteration', n, 'we flag', (worstCrossAnt[0],antpol)
            elif worstDeadCutRatio > worstCrossCutRatio and worstDeadCutRatio > 1.0:
                self.xants.append(worstDeadAnt)
                self.deadAntsRemoved.append(worstDeadAnt)
                self.removalIter[worstDeadAnt] = n
                if verbose:
                    print 'On iteration', n, 'we flag', worstDeadAnt
            else:
                break

    def save_antenna_metrics(self, metricsJSONFilename):
        '''Saves all cut decisions and meta-metrics in a human-readable JSON that can be loaded 
        back into a dictionary using hera_qm.ant_metrics.load_antenna_metrics().'''
        
        if not hasattr(self, 'xants'): 
            raise KeyError('Must run AntennaMetrics.iterative_antenna_metrics_and_flagging() first.')
        
        allMetricsData = {'xants': str(self.xants)}
        allMetricsData['ants_removed_as_crossed'] = str(self.crossedAntsRemoved)
        allMetricsData['ants_removed_as_dead'] = str(self.deadAntsRemoved)
        allMetricsData['final_metrics'] = str(self.finalMetrics)
        allMetricsData['all_metrics'] = str(self.allMetrics)
        allMetricsData['final_mod_z_scores'] = str(self.finalModzScores)
        allMetricsData['all_mod_z_scores'] = str(self.allModzScores)
        allMetricsData['removal_iteration'] = str(self.removalIter)
        allMetricsData['cross_pol_z_cut'] = str(self.crossCut)
        allMetricsData['dead_ant_z_cut'] = str(self.deadCut)
        
        with open(metricsJSONFilename, 'w') as outfile:
            json.dump(allMetricsData, outfile, indent=4)