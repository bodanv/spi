import pvlib
from pvlib import tracking, pvsystem, location, modelchain
from pvlib.pvsystem import PVSystem, FixedMount
from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS
import requests
import pandas as pd
from datetime import datetime, timedelta


"""
Useful link:
https://www.meteoblue.com/en/weather-api/forecast-api/index?apikey=nKY6EmU42hDkbu7H&packages%5B%5D=basic-1h&packages%5B%5D=basic-day&packages%5B%5D=solar-1h&tz=&format=json&temperature=C&windspeed=kmh&precipitationamount=mm&winddirection=degree&forecast_days=none&history_days=none

https://my.meteoblue.com/packages/basic-1h_solar-1h?apikey=t8NR5B2MKeXWilSL&lat=47.5584&lon=7.57327&asl=279&format=json
API OPTIONS = BASIC 1H, SOLAR 1H
"""

def get_location_data(lat, lon):
  """
  Read query from Meteoblue API. and obtain relevant weather data for the next 24 hours in 15 minute intervals.

  Parameters:
  ---------
  lat: latitude (decimal GPS coordinate). single numeric value
  lon: longitude (decimal GPS coordinate). single numeric value

  Output:
  ----------
  weather: Pandas Dataframe with data on temperature, GHI, DNI, DHI,
  wind speed, wind direction, precipitation, snow fraction, snow load.
  """

  response = requests.get("https://my.meteoblue.com/packages/basic-1h_solar-1h?apikey=t8NR5B2MKeXWilSL&lat="+str(lat)+"&lon="+str(lon)+"&asl=279&format=json")

  #Time
  time = pd.to_datetime( response.json()['data_1h']['time'][24:48] ) #take a list of datetime values and convert them in Pandas datetime format

  #temperature
  temperature = response.json()['data_1h']['temperature'][24:48]

  #Irradiance
  GHI = response.json()['data_1h']['ghi_instant'][24:48]
  DNI = response.json()['data_1h']['dni_instant'][24:48]
  DHI = response.json()['data_1h']['dif_instant'][24:48]

  #Wind speed and direction
  wind_speed = response.json()['data_1h']['windspeed'][24:48]
  wind_direction = response.json()['data_1h']['winddirection'][24:48]

  #Precipitation and snow
  precipitation = response.json()['data_1h']['precipitation'][24:48]
  snow_fraction = response.json()['data_1h']['snowfraction'][24:48]
  snow_load = [precipitation[t]*snow_fraction[t] for t in range(24)]

  #Store weather data in Pandas Dataframe
  weather = pd.DataFrame(index = time, columns = ['temperature', 'ghi', 'dni', 'dhi', 'wind_speed', 'wind_direction', 'precipitation', 'snow_fraction', 'snow_load'])
  weather.index = pd.to_datetime(weather.index)
  weather['temperature'] = temperature
  weather['ghi'] = GHI
  weather['dni'] = DNI
  weather['dhi'] = DHI
  weather['wind_speed'] = wind_speed
  weather['wind_direction'] = wind_direction
  weather['precipitation'] = precipitation
  weather['snow_fraction'] = snow_fraction
  weather['snow_load'] = snow_load

  return [time, weather]

def create_time_series():
  """
  Function returns a Pandas timeseries of datetime values of the next day.
  Resolution: Hourly (1h)
  When the function is called at day YYYY-MM-DD, the timeseries starts at YYYY-MM-DD+1 00:00  and ends YYYY-MM-DD+1 23:00.
  Format: Pandas Datetime.
  """
  # Get the current date and time
  now = datetime.now()

  # Calculate the start and end dates for the time series
  start_date = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
  end_date = start_date + timedelta(days=1) - timedelta(hours=1)

  # Generate the datetime values with a resolution of 1 hour
  time_values = pd.date_range(start=start_date, end=end_date, freq='1H')

  # Format the datetime values as strings using the specified format
  time_strings = time_values.strftime('%Y-%m-%d %H:%M')

  # Create a Pandas time series using the formatted datetime values
  time_series = pd.to_datetime(time_strings)


  return time_series

class DiscontoniousDualAxisTrackerMount(pvsystem.AbstractMount):
  """
  The class inherits features from the Abstract mount class.
  It is used to define features of the discountonuous dual axis solar tracker.
  """
  def get_orientation(self, solar_zenith, solar_azimuth):
    """
    Receives data about the solar azimuth and solar zenith angles at an arbitrary time step.
    Based on this data, it calculates the zenith and azimuth angles in which the solar tracker should be fixed
    during each time step with length 1 h

    Parameters:
    ---------
    solar_zenith: list of solar zenith angle values (in deg) for time steps in a given time period.
    solar_azimuth: list of solar azimuth angle values (in deg) for time steps in a given time period. (N=0, E=90, S=180, W=270)
    dt: length (in hours) of a single time step in the analyzed time period.

    Output:
    ---------
    tilt_and_azimuth: Pandas Dataframe with information about the position of the solar tracker. Columns = {tilt, azimuth}
      - tilt: angle (in deg) relative to horizontal surface. List of values for the tilt at which the tracker should be fixed for each time step with length dt.
      - azimuth: angle (in deg) relative to south at which the tracker should be fixed for each time step with length dt.

    """
    # no rotation limits, no backtracking
    zenith_subset = solar_zenith.resample('1h').first() #resample the data to a temporal resolution of dt
    azimuth_subset = solar_azimuth.resample('1h').first() #resample the data to a temporal resolution of dt

    tilt = zenith_subset.reindex(solar_zenith.index, method='ffill')
    azimuth = azimuth_subset.reindex(solar_azimuth.index, method='ffill')

    tilt_and_azimuth = pd.DataFrame(data={'surface_tilt': tilt, 'surface_azimuth': azimuth})

    return tilt_and_azimuth

def get_tracker_position(lat, lon, time_interval, mount_type):
  """
  Function that returns information about the position of the solar tracker (tilt and azimuth).

  Parameters:
  ---------
  lat: latitude (decimal GPS coordinate). single numeric value
  lon: longitude (decimal GPS coordinate). single numeric value
  time_interval: list of datetime values for the analyzed period. The position of the tracker is calculated for each time step in the period.
  mount_type: string specifying the type of mounting. Can be equal to 'fixed' or 'dual_axis'.

  Output:
  ---------
  tracker_data: Pandas Dataframe with list (series) of tilt and azimuth values (deg) of the solar tracker. Info can be used as input for the position of the solar tracker
  """

  loc = location.Location(lat, lon) #get features of the geographical position
  solar_position = loc.get_solarposition(time_interval) #for this geographical position and time_interval, calculate solar position
  solar_position[solar_position['apparent_elevation']<0] = 0

  if (mount_type == 'dual_axis'):
    mount = DiscontoniousDualAxisTrackerMount()
    tracker_data = mount.get_orientation(solar_position.apparent_zenith, solar_position.azimuth) #calculate position of tracker
    tracker_data['surface_tilt'] = tracker_data['surface_tilt'].apply(lambda x: 30 if x>30 else x).values #limit tilt based on mechanical structure

  if (mount_type == 'fixed'):
    mount = FixedMount(surface_tilt = 30, surface_azimuth = 180)
    tracker_data = mount.get_orientation(solar_position.apparent_zenith, solar_position.azimuth) #calculate position of tracker

  if ((mount_type != 'fixed') & (mount_type != 'dual_axis')):
    print("ERROR: The mounting type you specified is not supported. \n Mounting type can be 'fixed' or 'dual_axis.")

  return tracker_data

def get_tracker_poa_global(lat, lon, time_interval, tracker_data, weather):
  """
  The function calculates the Point of Array (POA) irradiance of a PV generator.  a given location time period, tracking system and weather data input.

  Parameters:
  ---------
  lat: latitude (decimal GPS coordinate). single numeric value
  lon: longitude (decimal GPS coordinate). single numeric value
  time_interval: list of datetime values for the analyzed period
  tracker_data: Pandas Dataframe with list (series) of tilt and azimuth values (deg). Info can be used as input for the position of the solar tracker

  Output:
  --------
  tracker_poa: Global POA irradiance for the solar panel (array) moved by the solar tracker. Info can be used as input for calculating the PV output
  """

  loc = location.Location(lat, lon) #get features of the geographical position
  solar_position = loc.get_solarposition(time_interval) #for this geographical position and time_interval, calculate solar position

  df_poa = pvlib.irradiance.get_total_irradiance(
      surface_tilt=tracker_data['surface_tilt'],
      surface_azimuth=tracker_data['surface_azimuth'],  # facing South
      dni=weather['dni'],
      ghi=weather['ghi'],
      dhi=weather['dhi'],
      solar_zenith=solar_position['apparent_zenith'],
      solar_azimuth=solar_position['azimuth'],
      model='isotropic')

  tracker_poa = df_poa['poa_global']

  return tracker_poa

def calculate_pv_generation(tracker_poa, weather):
  """
  Calculates AC and DC PV generation of a PV generator with fixed (pre-defined) parameters.

  Parameters:
  ---------
  tracker_poa: Point of Array (POA) irradiance at the surface of the PV generator of one day. Type: Pandas dataframe.
  weather:
    - if weather is forecasted using meteoblue: Data on temperature, GHI, DNI, DHI, wind speed, wind direction, precipitation, snow fraction, snow load.
    - if weather is not forecasted: Clearsky weather data obtained using loc.get_clearsky(time)

  Output:
  --------
  pv_power: Hourly DC and AC electricity generation of the PV generator. Type: Pandas Dataframe. Columns = ['dc', 'ac'].
  """

  parameters = pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS['sapm']['open_rack_glass_polymer']

  cell_temperature = pvlib.temperature.sapm_cell(tracker_poa,
                                               weather['temperature'].values,
                                               weather['wind_speed'].values,
                                               **parameters)

  gamma_pdc = -0.004  # divide by 100 to go from %/°C to 1/°C
  nameplate = 12e3 #12 kWp capacity
  pdc0 = 10000/0.96  # 10 kW inverter capacity with 0.96 efficiency

  pv_power = pd.DataFrame(index = tracker_poa.index, columns = [['dc', 'ac']])
  pv_power['dc'] = pvlib.pvsystem.pvwatts_dc(tracker_poa, cell_temperature, nameplate, gamma_pdc).values
  pv_power['ac'] = pvlib.inverter.pvwatts(pv_power['dc'], pdc0).values

  return pv_power

def main(lat, lon, mount_type, product_version):


    if (product_version == 'with_forecast'):
      # Read weather forecast
      [time, weather] = get_location_data(lat, lon)

      # Get solar tracker position for the next day
      tracker_data = get_tracker_position(lat, lon, time, mount_type)

      # Calculate POA irradiance for the solar panels mounted to the tracker
      tracker_poa = get_tracker_poa_global(lat, lon, time, tracker_data, weather)

      # Calculate DC and AC PV generation for the PV system with the specific solar tracker
      pv_power = calculate_pv_generation(tracker_poa, weather)


    if (product_version == 'without_forecast'):
      # Read weather forecast
      loc = location.Location(lat, lon)
      time = create_time_series()
      weather = loc.get_clearsky(time)

      # Get solar tracker position for the next day
      tracker_data = get_tracker_position(lat, lon, time, mount_type)

      # Calculate POA irradiance for the solar panels mounted to the tracker
      tracker_poa = get_tracker_poa_global(lat, lon, time, tracker_data, weather)

      # Calculate DC and AC PV generation for the PV system with the specific solar tracker
      tmy = pvlib.iotools.get_pvgis_tmy(lat, lon)
      df = pd.DataFrame(tmy[0])
      df.index = pd.to_datetime(df.index)
      if(time[0].day == time[23].day):
        weather = df[(df.index.day == time[0].day) & (df.index.month == time[0].month)]
        weather = weather.groupby(weather.index.hour).mean()
        weather.rename(columns={"temp_air": "temperature"}, inplace = True)
        pv_power = calculate_pv_generation(tracker_poa, weather)
      else:
        print("Error: Timeseries contains more than one day")



    return [tracker_data, pv_power]

# Specify the latitude and longitude
lat = 41.9965
lon = 21.4314

[tracker_data_fixed, pv_power_fixed] = main(lat, lon, 'fixed', 'with_forecast')
[tracker_data_dual_axis, pv_power_dual_axis] = main(lat, lon, 'dual_axis', 'with_forecast')
