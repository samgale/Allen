# -*- coding: utf-8 -*-
"""
Created on Wed Mar 11 13:02:06 2020

@author: chelsea.strawder

My hope is to combine and condense all of the data analysis functions into a single file
that we can then use to analyze the session data in a simpler script 
"""

import fileIO, h5py
import numpy as np
import pandas as pd
from nogoData import nogo_turn
from ignoreTrials import ignore_trials
from collections import defaultdict


def import_data():
    f = fileIO.getFile(rootDir=r'\\allen\programs\braintv\workgroups\nc-ophys\corbettb\Masking')
    d = h5py.File(f)
    return d

def extract_vars(data):
    return {key: data[str(key)][()] for key in data.keys()}
    
def create_vars(dn):
    for key,val in dn.items():   #work in progress, if even possible
        globals()
        exec (key + '= val')
        

def create_df(d):   #contrast, target, mask    
    
##pull all of the relevant data to create a dataframe object 

    fi = d['frameIntervals'][:]
    framerate = int(np.round(1/np.median(fi)))
    
    def convert_to_ms(value):
        return np.round(value * 1000/framerate).astype(int)
    
    trialResponse = d['trialResponse'][:]
    end = len(trialResponse)
    trialRewardDirection = d['trialRewardDir'][:end]
    trialTargetFrames = d['trialTargetFrames'][:end]
    trialTargetContrast = d['trialTargetContrast'][:end]
    
    trialOpenLoopFrames = d['trialOpenLoopFrames'][:end]
    if len(np.unique(trialOpenLoopFrames)>1):
        pass
        
    #    preStimFrames = d['preStimFramesFixed'][()]
    #    preStimVar = d['preStimFramesVariableMean'][()]              
    #    openLoopFrames = d['openLoopFramesFixed'][()]
    #    openLoopVar = d['openLoopFramesVariableMean'][()]
    #    openLoopMax = d['openLoopFramesMax'][()]
      
    trialStartFrame = d['trialStartFrame'][:end]
    trialStimStartFrame = d['trialStimStartFrame'][:]
    trialResponseFrame = d['trialResponseFrame'][:end] 
    quiescentMoveFrames = [q for q in d['quiescentMoveFrames'][:] if q<trialStimStartFrame[-1]]
    
    maxResp = d['maxResponseWaitFrames'][()]
    deltaWheel = d['deltaWheelPos'][:]                      
    repeats = d['trialRepeat'][:end]
    nogoWait = d['nogoWaitFrames'][()]
        
    maskOnset = convert_to_ms(d['maskOnset'][()])
    trialMaskOnset = convert_to_ms(d['trialMaskOnset'][:end])
    trialMaskContrast = d['trialMaskContrast'][:end]

    
### process & clean data
    for i, target in enumerate(trialTargetFrames):  # this is needed for older files nogos are randomly assigned a dir
        if target==0:
            trialRewardDirection[i] = 0
    
    nogos = [i for i, (rew, con) in enumerate(zip(trialRewardDirection, trialMaskContrast)) if rew==0 and con==0]
   
    if np.any(trialMaskOnset>0):
        targetOnlyVal = maskOnset[-1] + round(np.mean(np.diff(maskOnset)))  # assigns targetOnly condition an evenly-spaced value from soas
        maskOnset = np.append(maskOnset, targetOnlyVal)                     # makes final value the targetOnly condition
            
        for i, (mask, trial) in enumerate(zip(trialMaskOnset, trialTargetFrames)):   # filters target-Only trials 
            if trial>0 and mask==0:
                trialMaskOnset[i]=targetOnlyVal      
    
    trialLength = trialResponseFrame - trialStimStartFrame

#entire wheel trace from trial start to the max Length of trial
    totalWheel = [deltaWheel[start:stim+openLoop+maxResp] for (start,stim, openLoop) in 
                  zip(d['trialStartFrame'][()], trialStimStartFrame, trialOpenLoopFrames)]
    
    cumulativeWheel = [np.cumsum(mvmt) for mvmt in totalWheel]

    ignoreTrials = ignore_trials(d)
    turns, inds = nogo_turn(d)      #for both of these, [0]=nogos, [1]=maskOnly                    
    
    
    qDict = defaultdict(list)
    for i, (start,stimStart) in enumerate(zip(trialStartFrame, trialStimStartFrame)):
        for x in quiescentMoveFrames:    
            if start<x<stimStart:
                qDict[i].append(x)
          
    assert len(quiescentMoveFrames) == sum([len(qDict[x]) for x in qDict]), "Qframes Error"
                      
### Create dataframe
                
    data = list(zip(trialRewardDirection, trialResponse, 
                    trialStartFrame, trialStimStartFrame, trialResponseFrame))

    index = range(len(trialResponse))
    df = pd.DataFrame(data, 
                      index=index, 
                      columns=['rewDir', 'resp', 'trialStart', 'stimStart', 'respFrame'])
    
    df['trialLength'] = convert_to_ms(trialLength)
    
    df['mask'] = trialMaskContrast
    df['soa'] = trialMaskOnset
    #df['maskLength'] = convert_to_ms(d['trialMaskFrames'][:end])
    df['maskContrast'] = trialMaskContrast

    df['targetLength'] = convert_to_ms(trialTargetFrames)
    df['targetContrast'] = trialTargetContrast
    
    df['nogo'] = False
    for i in nogos:
        df.loc[i, 'nogo'] = True
   
    def fill():
        return np.zeros(len(trialResponse)).astype(int)
    
    df['nogoMove'] = fill()
    df['maskOnlyMove'] = fill()
          
    for e, col in enumerate(('nogoMove', 'maskOnlyMove')):
        for (i,turn) in zip(inds[e], turns[e]):
            df.at[i, col] = turn
    
    df['ignoreTrial'] = False   
    for i in ignoreTrials:
        df.loc[i, 'ignoreTrial'] = True
        
    df['repeat'] = repeats    
    
    df['Qviolations'] = fill()
    for key,val in qDict.items():
        df.at[key, 'Qviolations'] = len(val)
        
    df['WheelTrace'] = cumulativeWheel
    
    return df
