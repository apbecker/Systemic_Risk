import pandas as pd
import numpy as np

# Functions from the model        
def Q(x):
    return 1. - 2**(-x/100.)
   
    
# Function to select from DataFrame
def dfSelecter(df, rows=None, columns=None):
    if type(df) == pd.Series:
        df = df.to_frame().T

    if rows == None:
        if columns == None:
            return df.copy()
        else:
            try:
                return df.loc[:, columns]
            except KeyError:
                print "Name Error in column."
    else:
        if columns == None:
            try:
                return df.loc[rows]
            except KeyError:
                print "Name Error in row."
        else:
            try:
                return df.loc[rows, columns]
            except KeyError:
                try:
                    df.loc[:, columns]
                except KeyError:
                    print "Name Error in column."
                try:
                    df.loc[rows]
                except KeyError:
                    print "Name Error in row."

                    
# Extract identifier of asset class from column names                    
def ExtractAssetClass(col):
    return col[0:col.find("_")]

def ExtractAssetName(col):
    return col[col.find("_")+1:]


def RiskWeights(minmax):
    # Initialize dictionaries
    if minmax == "min":
        return {"1": 0.002, "2": 0.5, "3": 0.7, 
                "4-1": 0.4, "4-2": 0.8, "4-3": 1, "5": 1}
    elif minmax == "max":
        return {"1": 0.1, "2": 1, "3": 1.3, 
                "4-1": 0.8, "4-2": 1.2, "4-3": 1.3, "5": 2}
    else:
        # In case of input error, return minimum weights.
        return {"1": 0.002, "2": 0.5, "3": 0.7, 
                "4-1": 0.4, "4-2": 0.8, "4-3": 1, "5": 1}




class World(object):
    'Common base class for all realizations of stress test'
    # To be passed: Dataframe containing asset classes, name, capital
    # To be passed: Dataframe containing how much banks are invested where
    def __init__(self, data, structure, spread, other_spread, risk_dict, P, t_limit=200, abort_thr=5e-5):
        # Dataframe. Index: Banks, Columns: Asset classes, name, capital
        self._data = data
        self._prep_data = None
        # Geo-structure of banks' investments, usually inferred from sovereign debt
        self._structure = structure
        # Spreading parameters
        self._spread = spread
        self._other_spread = other_spread
        # Risk dictionary
        self._risk_dict = risk_dict
        self._sect_dict = \
            {"sov":"1_Sov", "fin":"2_Fin", "corp":"3_Corp", "ret_res":"4-1_Ret_Res", 
             "ret_rev":"4-2_Ret_Rev", "ret_sme":"4-3_Ret_SME", "cre":"5_CRE", "bank":"0_Bank"}
        
        self.P = P
        self.t_limit = t_limit
        self.abort_thr = abort_thr
        
        # Populate children
        self._assets = self.initAssets(self.getByAsset())
        self._banks  = self.initBanks(self._data)
        
        # Empty DataFrames to track spread of crisis
        self._evolution_banks  = pd.DataFrame(data=None, columns=None, index=[b for b in self._banks])
        self._evolution_assets = pd.DataFrame(data=None, columns=None, index=[a for a in self._assets])
        
    
    def getData(self):
        return self._data
    
    def setData(self, df):
        print "Protected."
        pass
    
    data = property(getData, setData)
    
    
    def getStructure(self):
        return self._structure
    
    def setStructure(self, df):
        print "Protected."
        pass
    
    structure = property(getStructure, setStructure)
    
    
    def getSectorDict(self):
        return self._sect_dict
    
    def setSectorDict(self, dict):
        print "Protected."
        pass
    
    sect_dict = property(getSectorDict, setSectorDict)
    
    
    def getBankEvo(self):
        return self._evolution_banks
    
    def setBankEvo(self, evo):
        self._evolution_banks = evo
    
    evolution_banks = property(getBankEvo, setBankEvo)
    
    
    def getAssetEvo(self):
        return self._evolution_assets
    
    def setAssetEvo(self, evo):
        self._evolution_assets = evo
    
    evolution_assets = property(getAssetEvo, setAssetEvo)
    
    
    
    def __str__(self):
        return 'Implementation'        
    
    
    def initBanks(self, data):
        banks = {}
        for bank in data.index.values:
            banks[bank] = Bank(bank, self.getName(bank),
                               self.getCapital(bank),
                               self.getByAsset(bank=bank),
                               self.getGeoStructure(bank=bank))

        for bank in banks:                
            obj = banks[bank]
            hol = obj.getHoldingsByAsset()
            rwa = hol.dot(self.getInitRiskWeights(self._assets))
            obj.capital = rwa * obj.capital
        
        self._prep_data = pd.DataFrame(data=None, columns=hol.columns)

        for bank in banks:
            self._prep_data = self._prep_data.append(banks[bank].getHoldingsByAsset())
            
        return banks
    
    
    def initAssets(self, data):
        assets = {}
        for asset in data.columns.values:
            assets[asset] = Asset(ExtractAssetClass(asset),
                                  asset, np.sum(data.loc[:, asset]))
            
        for asset in assets:
            obj = assets[asset]
            obj_ac = obj.getAssetClass()
            obj.riskweight = self._risk_dict[obj_ac]
            obj.staticriskweight = obj.riskweight
            if obj_ac == "1":
                obj.spread = self._spread.loc[obj.getCountry(), "Q"]
            else:
                obj.spread = self._other_spread
                
        return assets
    
    
    def initShockAssets(self, assets, shocksector, shockcountries, shockfactor):
        shocklist = [self.sect_dict[shocksector.lower()] + "_" + c for c in shockcountries]
        for asset in shocklist:
            obj = assets[asset]
            obj.riskweight = np.minimum(shockfactor*obj.riskweight, 2)
        return "Shock set for countries."
    
    
    def initShockBanks(self, banks, shockbanks, capitalreducedby):
        for bank in shockbanks:
            obj = banks[bank]
            obj.capital = obj.capital * (1.-capitalreducedby)
        return "Shock set for banks."
    
    
    def propShockToBanks(self, banks, assets_df, time):
        t = str(time)
        df = self.evolution_banks
        
        banks_df = pd.DataFrame(data=[[bank, banks[bank].getCapital().values[0][0]]
                                      for bank in banks],
                                columns=["bank", "capital"]).set_index("bank")
        banks_df.loc[:, "rwa"] = self._prep_data.dot(assets_df.loc[:, "rws"])

        df.loc[:, "W_"+t] = banks_df.loc[:, "rwa"]
        df.loc[:, "R_"+t] = banks_df.loc[:, "capital"] / banks_df.loc[:, "rwa"]
        
        self.evolution_banks = df.sort_index()
        return self.evolution_banks, banks
    
    def propShockToAssets(self, assets, assets_df, time):
        t = str(time)
        df = self.evolution_assets
        
        omega_s = pd.DataFrame(data=None, columns=["omega", "q"], index=self.evolution_assets.index)
        
        if time > 1:
            delta_R = self.evolution_banks.loc[:, "R_"+str(time-1)] / self.evolution_banks.loc[:, "R_"+str(time-3)]
            delta_R = delta_R.apply(self.P)
            delta_R = delta_R.dot(self.getByAsset()) / np.sum(self.getByAsset())
            
            omega_s.loc[:, "q"] = assets_df.loc[:, "q"]
            omega_s.loc[:, "omega"] = 1 - omega_s.loc[:, "q"]*(1-delta_R)
            
            df.loc[:, "r_"+t] = assets_df.loc[:, "rws"] / omega_s.loc[:, "omega"]
            df.loc[:, "r_"+t] = np.minimum(df.loc[:, "r_"+t].to_frame(), 2)
            
            
        else:
            df.loc[:, "r_"+t] = assets_df.loc[:, "rws"]
            
            
        for asset in assets:             
            assets[asset].riskweight = df.loc[asset, "r_"+t]
            
        self.evolution_assets = df.sort_index()
        return self.evolution_assets, assets
    
    
    def runShock(self, banks, assets, shocksector, shockcountries, shockfactor):
        return self.runShockAssets(banks, assets, shocksector, shockcountries, shockfactor)
        
    
    def runShockAssets(self, banks, assets, shocksector, shockcountries, shockfactor):
        assets_df = pd.DataFrame(data=[[asset, assets[asset].getSpread(), 
                                        assets[asset].riskweight, assets[asset].getValue()]
                                       for asset in assets],
                                 columns=["asset", "q", "rws", "value"]).set_index("asset")
        
        evo_a, assets = self.propShockToAssets(assets, assets_df, 0)
        evo_b, banks  = self.propShockToBanks(banks, assets_df, 0)
        self.initShockAssets(assets, shocksector, shockcountries, shockfactor)
        t = 0
        while True:
            t = t+1
            assets_df = pd.DataFrame(data=[[asset, assets[asset].getSpread(), 
                                            assets[asset].riskweight, assets[asset].getValue()]
                                           for asset in assets],
                                     columns=["asset", "q", "rws", "value"]).set_index("asset")
            if np.mod(t,2) == 1:
                evo_a, assets = self.propShockToAssets(assets, assets_df, t)
            else:
                evo_b, banks  = self.propShockToBanks(banks, assets_df, t)
                
                abort_df = evo_b.filter(like="R_")
                if max(abort_df.iloc[:, -2] - abort_df.iloc[:, -1]) <= self.abort_thr:
                    break
                if t >= self.t_limit:
                    break
        
        return evo_a, evo_b, t
    
        
    def runShockBanks(self, banks, assets, shockbanks, capitalreducedby):
        if type(shockbanks) == str:
            if shockbanks == "All":
                shockbanks = banks.keys()
            else:
                shockbanks = [b for b in banks.keys() if b[0:2] == shockbanks]
        elif len(shockbanks[0]) == 2:
            shockbanks = [b for b in banks.keys() if b[0:2] in shockbanks]

        
        assets_df = pd.DataFrame(data=[[asset, assets[asset].getSpread(), 
                                        assets[asset].riskweight, assets[asset].getValue()]
                                       for asset in assets],
                                 columns=["asset", "q", "rws", "value"]).set_index("asset")
        
        evo_a, assets = self.propShockToAssets(assets, assets_df, 0)
        evo_b, banks  = self.propShockToBanks(banks, assets_df, 0)
        self.initShockBanks(banks, shockbanks, capitalreducedby)
        t = 0
        while True:
            t = t+1
            assets_df = pd.DataFrame(data=[[asset, assets[asset].getSpread(), 
                                            assets[asset].riskweight, assets[asset].getValue()]
                                           for asset in assets],
                                     columns=["asset", "q", "rws", "value"]).set_index("asset")
            if np.mod(t,2) == 1:
                evo_a, assets = self.propShockToAssets(assets, assets_df, t)
            else:
                evo_b, banks  = self.propShockToBanks(banks, assets_df, t)
                
                abort_df = evo_b.filter(like="R_")
                if max(abort_df.iloc[:, -2] - abort_df.iloc[:, -1]) <= 5e-5:
                    break
                if t >= 200:
                    break
        
        return evo_a, evo_b, t
    
    
    def getBanks(self):
        return self._banks
    
    
    def getAssets(self):
        return self._assets
    
    
    # All investments etc.
    def getByAssetClass(self, bank=None, asset_class=None):
        
        # List of columns in the data frame which are not asset-related
        droplist = ["Capital", "Name"]
        df = self._data
        
        for drop in droplist:
            try:
                df = df.drop(drop, axis=1)
            except:
                pass

        return dfSelecter(df, rows=bank, columns=asset_class)
        
        
    # Investments 
    def getByAsset(self, asset_class=None, bank=None, asset=None):
        # Data frame with banks' investments
        df = self.getByAssetClass(bank=bank, asset_class=asset_class)
        # Geo-structure of banks' investments
        weights_df = self.getGeoStructure(bank=bank)
        
        
        # Make sure we didn't pass a series
        if type(df)==pd.Series:
            df = df.to_frame().T
        if type(weights_df)==pd.Series:
            weights_df = weights_df.to_frame().T
        
        
        # Multiply each asset class to split up by country
        asset_classes = df.columns
        df_list = [weights_df.multiply(df.loc[:, ac], axis=0) 
                   for ac in asset_classes]
        
        # Concatenate data frames for each asset class and rename columns
        full_df = pd.concat(df_list, axis=1)
        full_df.columns = [col+"_"+ind for col in asset_classes 
                           for ind in weights_df.columns]
        return full_df
        
    
    # Read Capital information
    def getCapital(self, bank=None):    
        return dfSelecter(self._data, rows=bank, columns="Capital")

    
    # Names of Banks
    def getName(self, bank=None):    
        return dfSelecter(self._data, rows=bank, columns="Name")
    
    
    # Geo-structures of banks
    def getGeoStructure(self, bank=None):
        return dfSelecter(self._structure, rows=bank)
    
    
    def getInitRiskWeights(self, assets):
        try:
            rw = pd.DataFrame(data=[[asset, assets[asset].riskweight] 
                                    for asset in assets],
                              columns=["asset", "weight"])
            return rw.set_index("asset")
        except:
            print "No risk weights set"
            pass


    
class Bank(World):
    'Class for banks in the model'
    # Initialize with name, country, holdings and capital ratio (since this is what we know)
    # When the stress test scenario is initialized, the capital is updated using the ratio 
    # and the RWA.
    
    def __init__(self, bankid, name, capital, data, structure):
        self._bankid = bankid
        self._name = name
        self._capital = capital
        self._data = data
        self._structure = structure
        
        
    def __str__(self):
        return '{}, capital {}'.format(self._name, self._capital)  
    
    
    def getData(self):
        return self._data
    
    def setData(self, df):
        print "Protected."
        pass
    
    data = property(getData, setData)
    
    
    def getStructure(self):
        return self._structure
    
    def setStructure(self, df):
        print "Protected."
        pass
    
    structure = property(getStructure, setStructure)

    
    # Name of the bank
    def getBankID(self):
        return self._bankid
    
    
    # Name of the bank
    def getName(self):
        return self._name

    def setName(self, n):
        self._name = n
        
    name = property(getName, setName)
    
    
    # WARNING: Due to the structure of the available data, 
    # initialization begins with ratio!
    def getCapital(self):
        return self._capital
    
    def setCapital(self, c):
        self._capital = c
        
    capital = property(getCapital, setCapital)
    
    
    def getRWA(self, rws):
        return self.getHoldingsByAsset().dot(rws)
    
    
    def getHoldingsByAssetClass(self, asset_class=None): 
        df = self.getHoldingsByAsset()
        valid_sectors = ["1_Sov", "2_Fin", "3_Corp", "4-1_Ret_Res", "4-2_Ret_Rev", "4-3_Ret_SME", "5_CRE"]
        byasset = []
        sect = valid_sectors[0]
        
        for sec in valid_sectors:
            byasset.append([sec, df.filter(like=sec).apply(np.sum, axis=1).values[0]])
        
        df = pd.DataFrame(data=byasset, columns=["Sector", "Holdings"]).set_index("Sector")
        return dfSelecter(df, rows=asset_class)
        
    
    
    def getHoldingsByAsset(self, asset_class=None, asset=None):
        # Data frame with banks' investments
        df = self.getByAssetClass(asset_class=asset_class)
        return df
    
    
    def getGeoStructure(self):
        return dfSelecter(self._structure, rows=self.getBankID())

    
    # EBA Bank ID
    def getBankID(self):
        return self._bankid
    
    
    # Country in which the bank is headquartered
    def getCountry(self):
        return self._bankid[0:2]
    
    
    
class Asset(World):
    'Class for assets in the model'
    # Initialize with asset class, name of asset, value, who holds it, but w/o risk weights
    def __init__(self, asset_class, name, value, spread=None, riskweight=None):
        self._asset_class = asset_class
        self._name = name
        self._country = name[-2:]
        self._value = value
        self._marketvalue = value
        self._spread = spread
        self._riskweight = riskweight
        self._staticriskweight = riskweight
        
    def __str__(self):
        return 'Name {}, class {}, country {}, value {}, weight {}'.\
            format(self.getName(), self.getAssetClass(), self.getCountry(), self.getValue(), self.getRiskWeight())
            
            
    # Name of asset
    def getName(self):
        return self._name
    
    
    # Country of asset, last two characters of name
    def getCountry(self):
        return self._country
    
    
    # Asset class, including sovereign debt, finance, commercial, retail and real estate.
    def getAssetClass(self):
        return self._asset_class
    
    
    # Total value of asset combining holdings of all banks
    def getValue(self):
        return self._value
    
        
    def getMarketValue():
        pass
    
    def setMarketValue(self, s):
        pass
        
    marketvalue = property(getMarketValue, setMarketValue)
    
        
    def getSpread(self):
        return self._spread
    
    def setSpread(self, s):
        self._spread = s
        
    spread = property(getSpread, setSpread)
    
    
    # Output risk weight or risk factor of asset at current moment
    def getRiskWeight(self):
        return self._riskweight
    
    # Function to update risk factor in crisis propagation
    def setRiskWeight(self, r):
        self._riskweight = r
        
    riskweight = property(getRiskWeight, setRiskWeight)

    
    # staticriskweight is the risk factor which was used to initialize asset
    def getStaticRiskWeight(self):
        return self._staticriskweight
        
    def setStaticRiskWeight(self, r):
        self._staticriskweight = r
        
    staticriskweight = property(getStaticRiskWeight, setStaticRiskWeight)    
    
    
    # Factor by which the risk factor has increased compared to initial state
    def getCrisisLevel(self):
        return self.riskweight/self.staticriskweight
    