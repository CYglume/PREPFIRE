import numpy as np
import xarray as xr

def rh_calc(td, t):
    """
    Calculate relative humidity from temperature and dew point temperature.
    
    Parameters:
    -----------
    td : float or numpy.ndarray
        Dew point temperature in Celsius
    t : float or numpy.ndarray
        Temperature in Celsius
        
    Returns:
    --------
    float or numpy.ndarray
        Relative humidity as a percentage
    """
    return 100 * np.exp((17.625 * td) / (243.04 + td)) / np.exp((17.625 * t) / (243.04 + t))

def vpd_calc(t, rh):
    """
    Calculate vapor pressure deficit from temperature and relative humidity.
    
    Parameters:
    -----------
    t : float or numpy.ndarray
        Temperature in Celsius
    rh : float or numpy.ndarray
        Relative humidity as a percentage
        
    Returns:
    --------
    float or numpy.ndarray
        Vapor pressure deficit in kPa
    """
    svp = 0.61121 * np.exp((18.678 - t/234.5) * (t/(257.14 + t)))
    return svp * (1 - rh/100)

def dfmc_calc(t, rh):
    """
    Calculate dead fuel moisture content from temperature and relative humidity.
    
    Parameters:
    -----------
    t : float or numpy.ndarray
        Temperature in Celsius
    rh : float or numpy.ndarray
        Relative humidity as a percentage
        
    Returns:
    --------
    float or numpy.ndarray
        Dead fuel moisture content as a percentage
    """
    return 4.37 + 0.161*rh - 0.1*t - 0.027*rh

def dfmc_vpd_calc(vpd):
    """
    Calculate dead fuel moisture content from vapor pressure deficit.
    
    Parameters:
    -----------
    vpd : xarray.DataArray
        Vapor pressure deficit in kPa
        
    Returns:
    --------
    xarray.DataArray
        Dead fuel moisture content as a percentage
    """
    return 0.8 + 20.43 * np.exp((-0.34*vpd))