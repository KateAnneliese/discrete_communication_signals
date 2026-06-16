#!/usr/bin/env python
# coding: utf-8

# ## Importing Libraries and Setting Pandas Features

# In[114]:


# import all necessary libraries
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import pandas as pd
import time
import random
import os
import re
from pathlib import Path


# In[115]:


# set pandas display setting
pd.set_option("display.max_colwidth", None)
pd.set_option("display.max_rows", None)
pd.set_option("display.width", None)


# ## Cricket Dataframe

# In[116]:


# create a variable, url, to store the link to the Singing Insects of North America (SINA) cricket list webpage
url = 'https://orthsoc.org/sina/cricklist.htm'
# define HTTP request headers for reference later
headers = {
    "User-Agent": (
        "AcademicResearchBot"
        "(collecting data for non-commercial communication signals research project)"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive"
}


# In[117]:


# this cell uses the requests library and the BeautifulSoup library to get the HTML code behind the SINA cricket list webpage

response = requests.get(url, headers = headers)
soup = BeautifulSoup(response.text, 'html.parser')


# In[118]:


# this cell retrieves all cricket species names and the URLs to their corresponding pages from the SINA cricket list webpage
# this cell also appends a dictionary with each species name and their URL to cricket_species_list

cricket_species_list = []
for species in soup.find_all("h3", class_="species"):
    a_tag = species.find("a")
    if a_tag:
        species_name = a_tag.get_text(strip = True)
        species_url = urljoin("https://orthsoc.org/sina/", a_tag["href"])
        cricket_species_list.append({"species": species_name, "url": species_url})


# In[119]:


# This cell uses the dictionaries stored in cricket_species_list to visit each individual cricket webpage.
# The code retrieves the spectrogram and audio clip from each individual cricket webpage.
# If it can locate the description of the audio file, the temperature at which the audio file was recorded, the
# location at which it was recorded, and/or the range map showing where that species is found, it also retrieves those.
# For every species, all data points found are put into a dictionary, which is appended to the list grouped_data

# create the list grouped_data and a stateful session object to be referenced later
cricket_grouped_data = []
session = requests.Session()
session.headers.update(headers)

# loop through all the cricket species contained in the list cricket_species_list using the urls
for species in cricket_species_list:

    r = session.get(species["url"], timeout=15)
    r.encoding = r.apparent_encoding
    soup = BeautifulSoup(r.text, "html.parser")
    species_name = species["species"]

    # attempt to locate the species' range map using the site's standard image table structrue
    map_large = None
    map_figure = soup.find("table", class_="images")

    if map_figure:
        # find the link associated with the map thumbnail
        map_link = map_figure.find("a", href=True)
        if map_link:
            href = map_link["href"]

            # construct the URL for the full-size map image
            match = re.search(r"(\d+)m\.htm", href, re.I)
            if match:
                code = match.group(1)
                href = f"{code}mc.gif"
                map_large = urljoin(species["url"], href)

    # if the map can't be found using the site's standard image table structure, search for a caption containing the word "map"
    if not map_large:
        for row in soup.find_all("tr"):
            caps = row.find_all("td", class_="captions")
            for idx, cap in enumerate(caps):
                # check whether the caption corresponds to a range map
                if "map" in cap.get_text(" ", strip=True).lower():
                    # try to retrieve information from the previous row, where the map should be stored
                    prev = row.find_previous_sibling("tr")
                    if not prev:
                        continue

                    imgs = prev.find_all("td", class_="images")
                    if idx >= len(imgs):
                        continue

                    # match the map caption to its corresponding image
                    link = imgs[idx].find("a", href=True)
                    if not link:
                        continue

                    href = link["href"]
                    # find the URL for the full-size map image
                    match = re.search(r"(\d+)m\.htm", href, re.I)
                    if match:
                        code = match.group(1)
                        href = f"{code}mc.gif"
                        map_large = urljoin(species["url"], href)
                    break
            if map_large:
                break

    # find all divs with recordings
    recording_blocks = soup.find_all(
        "div",
        class_=lambda x: x and "recording" in x
    )

    # loop through all the recordings found earlier
    for rec in recording_blocks:

        # extract the description from the previous recording block
        # the second recording is a clip of the first, so the description of the first provides
        # temperature and location for the second
        text = rec.get_text(" ", strip=True)

        if "recordingnopadding" in rec.get("class", []):
            prev_rec = rec.find_previous("div", class_="recording")

            if prev_rec:
                text = prev_rec.get_text(" ", strip=True)

        # extract audio file from the recording block
        audio = None
        audio_tag = rec.find("audio")
        if audio_tag:
            source = audio_tag.find("source", src=True)
            if source:
                audio = urljoin(species["url"], source["src"])

        # declare a spectrogram variable, initialized to "None" to prevent errors later
        spectrogram = None

        # loop through images in the recording block
        for img in rec.find_all("img", src=True):
            src = img["src"].lower()
            alt = (img.get("alt") or "").lower()

            combined = f"{src} {alt} {text.lower()}"

            # if the image is described as a spectrogram (or something similar), join the species url with the image source
            # and store it in the spectrogram variable
            if any(word in combined for word in [
                "spectrogram",
                "sonogram",
                "waveform",
                "graph",
                "graphed song"
            ]):
                spectrogram = urljoin(species["url"], img["src"])
                break

        # skip if nothing useful is found
        if not spectrogram:
            continue

        # attempt to extract temperature from description by searching for the "°" character
        temp = None
        if "°" in text:
            i = text.find("°")
            # remove any stray characters 
            temp = text[max(0, i - 5): i + 1].strip('abcdefghijklmnopqrstuvwxyz ')
            # encoding causes "Â" characters to show up before the "°", so remove those
            text = text.replace("Â", "")

        # attempt to extraction location from description using key words "from" and "in" that are usually found around the location
        loc = "No location found"

        if "from" in text:
            start = text.find("from") + 5
            end = text.find("°") if "°" in text else len(text)
            loc = text[start:end]

        elif "in" in text:
            start = text.find("in") + 3
            end = text.find("°") if "°" in text else len(text)
            loc = text[start:end]

        loc = loc.strip(" ,;.Â")

        # append all pieces of data to the grouped_data list as a dictionary
        cricket_grouped_data.append({
            "Species": species_name,
            "URL": species["url"],
            "Spectrogram": spectrogram,
            "Audio": audio,
            "Description": text,
            "Temperature": temp,
            "Location": loc,
            "Map": map_large
        })

    # courtesy pause so the SINA website doesn't get overwhelmed
    time.sleep(random.uniform(1, 2))


# In[120]:


# create a Pandas dataframe from the grouped_data lsit
cricket_df = pd.DataFrame(cricket_grouped_data)


# In[121]:


# rename the cricket_df columns
cricket_df.columns = ['Species', 'URL', 'Spectrogram', 'Audio_Link', 'Description of Whole Audio File', 'Temperature (°C)', 'Location', 'Map']


# In[ ]:


cricket_loc_list = []
for idx, row in cricket_df.iterrows():
    print(f"Current location: {row['Location']}")

    response = input("Type a replacement location: ").strip()

    if response:
        cricket_loc_list.append(response)
    else:
        cricket_loc_list.append(row['Location'])

print("Finished reviewing locations.")
cricket_loc_list


# In[129]:


cricket_df['Location'] = ['No location found',
 'Pettis County, MO',
 'Lake County, TN',
 'No location found',
 'No location found',
 'No location found',
 'Alachua County, Fla',
 'Big Pine Key, Monroe County, Fla',
 'Pima County, Ariz',
 'Pima County, Ariz',
 'No location found',
 'Eddy County, N. Mex',
 'Eddy County, N. Mex',
 'Eddy County, N. Mex',
 'No location found',
 'Cameron County, Tex',
 'Cameron County, Tex',
 'Dade County, Fla',
 'San Benito County, California',
 'Key Largo, Monroe County, Fla',
 'Key Largo, Monroe County, Fla',
 'Brewster County, Tex',
 'Brewster County, Tex',
 'Pima County, Ariz',
 'Pima County, Ariz',
 'Alachua County, Fla',
 'Westmoreland County, Va',
 'Alachua County, Fla',
 'Alachua County, Fla',
 'Alachua County, Fla',
 'Tulare County, Calif',
 'Millard County, Utah',
 'Millard County, Utah',
 'Cochise County, Ariz',
 'Cochise County, Ariz',
 'Jasper Ridge, San Matero County, Calif',
 'Mendocino County, Calif',
 'Torrance County, N. Mex',
 'Torrance County, N. Mex',
 'Jackson County, S. Dak',
 'Jackson County, S. Dak',
 'Cochise County, Ariz',
 'Cochise County, Ariz',
 'Alpine, San Diego County, Calif',
 'Alpine, San Diego County, Calif',
 'Pima County, Ariz',
 'Pima County, Ariz',
 'Coconino County, Ariz',
 'Coconino County, Ariz',
 'Alachua County, Fla',
 'Alachua County, Fla',
 'Dyer County, Tenn',
 'Worcester County, Mass',
 'Badlands National Park, Jackson County, S. Dak',
 'Brewster County, Tex',
 'Jeff Davis County, Tex',
 'Jeff Davis County, Tex',
 'Sinaloa, Mexico',
 'Sinaloa, Mexico',
 'Leon County, Fla',
 'Pope County, Ill',
 'Fla',
 'Santa Clara County, Calif',
 'Santa Clara County, Calif',
 'Doña Ana County, N. Mex',
 'Doña Ana County, N. Mex',
 'Maricopa County, Ariz',
 'Maricopa County, Ariz',
 'Maricopa County, Ariz',
 'Maricopa County, Ariz',
 'Neshoba County, Miss',
 'Austin, Tex',
 'Cameron County, Tex',
 'Cameron County, Tex',
 'Culberson County, Tex',
 'Culberson County, Tex',
 'Howard County, Tex',
 'Howard County, Tex',
 'Berrien County, Mich',
 'Santa Clara County, Calif',
 'Santa Clara County, Calif',
 'Hickman County, Ky',
 'San Diego County, Calif',
 'San Diego County, Calif',
 'San Diego County, Calif',
 'Cibola County, N. Mex',
 'Cibola County, N. Mex',
 'Highlands County, Fla',
 'Cumberland County, N.C.',
 'Hidalgo County, Tex',
 'No location found',
 'Levy Co., Fla.: Cedar Key',
 'Dade Co., Fla.: EVNP',
 'Monroe Co., Fla.: Key Largo',
 'Jefferson Co., W. Va',
 'Dade Co., Fla.: EVNP',
 'Martin Co., Fla',
 'Monroe Co., Fla.: Lower Keys',
 'Clay Co., Fla',
 'Manatee Co., Fla',
 'Lake Co., Tenn',
 'Monroe Co., Fla.: Flamingo',
 'Charlotte Co., Fla',
 'Monroe Co., Fla.: Key Largo',
 'Alachua Co., Fla',
 'Marshall Co., Okla',
 'Levy Co., Fla.: Shell Mound',
 'Monroe Co., Fla.: Sugarloaf Key',
 'Monroe Co., Fla',
 'Jefferson Co., Tex',
 'Hancock Co., Miss',
 'Hancock Co., Miss',
 'Dade Co., Fla',
 'Tyler Co., Tex',
 'Alachua Co., Fl',
 'Alachua Co., Fl',
 'Glynn Co., Ga',
 'Cameron Co., Tex',
 'Hidalgo Co., Texas',
 'Atzelsberg, Germany',
 'Trier, Germany',
 'No location found',
 'Heywood Co., N. Car',
 'Mercer County, New Jersey',
 'Alachua Co., Fla',
 'Notre Dame du Lac, Quebec',
 'Notre Dame du Lac, Quebec',
 'Livingston Co., Ky',
 'Berkeley County, West Virginia',
 'Lake County, TN',
 'Lake County, TN',
 'Lake Co., Tenn',
 'Levy Co., Fla',
 'Alleghany Co., N. Car',
 'No location found',
 'No location found',
 'No location found',
 'Santa Clara County, Palo Alto, Calif',
 'Santa Clara County, Palo Alto, Calif',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'Otero Co., N.M.',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found',
 'No location found']


# In[132]:


# save cricket_df using IPython magic
get_ipython().run_line_magic('store', 'cricket_df')


# ## Katydid Dataframe

# In[ ]:


# overwrite the url variable to store the link to the Singing Insects of North America (SINA) katydid list webpage
url = 'https://orthsoc.org/sina/katylist.htm'


# In[ ]:


# use the requests and BeautifulSoup libraries to get the HTML code for the katydid list webpage
response = requests.get(url, headers = headers)
katydid_soup = BeautifulSoup(response.text, 'html.parser')


# In[ ]:


# retrieve all katydid species names and urls, create a dictionary with them, and append them to katydid_species_list
katydid_species_list = []
for species in katydid_soup.find_all("h3", class_="species"):
    a_tag = species.find("a")
    if a_tag:
        species_name = a_tag.get_text(strip = True)
        species_url = urljoin("https://orthsoc.org/sina/", a_tag["href"])
        katydid_species_list.append({"species": species_name, "url": species_url})


# In[133]:


# This cell uses the dictionaries stored in katydid_species_list to visit each individual katydid webpage.
# The code retrieves the spectrogram and audio clip from each individual katydid webpage.
# If it can locate the description of the audio file, the temperature at which the audio file was recorded, the
# location at which it was recorded, and/or the range map showing where that species is found, it also retrieves those.
# For every species, all data points found are put into a dictionary, which is appended to the list grouped_data

# create the list grouped_data and a stateful session object to be referenced later
katydid_grouped_data = []
session = requests.Session()
session.headers.update(headers)

# loop through all the katydid species contained in the list katydid_species_list using the urls
for species in katydid_species_list:

    r = session.get(species["url"], timeout=15)
    r.encoding = r.apparent_encoding
    soup = BeautifulSoup(r.text, "html.parser")
    species_name = species["species"]

    # attempt to locate the species' range map using the site's standard image table structrue
    map_large = None
    map_figure = soup.find("table", class_="images")

    if map_figure:
        # find the link associated with the map thumbnail
        map_link = map_figure.find("a", href=True)
        if map_link:
            href = map_link["href"]

            # construct the URL for the full-size map image
            match = re.search(r"(\d+)m\.htm", href, re.I)
            if match:
                code = match.group(1)
                href = f"{code}mc.gif"
                map_large = urljoin(species["url"], href)

    # if the map can't be found using the site's standard image table structure, search for a caption containing the word "map"
    if not map_large:
        for row in soup.find_all("tr"):
            caps = row.find_all("td", class_="captions")
            for idx, cap in enumerate(caps):
                # check whether the caption corresponds to a range map
                if "map" in cap.get_text(" ", strip=True).lower():
                    # try to retrieve information from the previous row, where the map should be stored
                    prev = row.find_previous_sibling("tr")
                    if not prev:
                        continue

                    imgs = prev.find_all("td", class_="images")
                    if idx >= len(imgs):
                        continue

                    # match the map caption to its corresponding image
                    link = imgs[idx].find("a", href=True)
                    if not link:
                        continue

                    href = link["href"]
                    # find the URL for the full-size map image
                    match = re.search(r"(\d+)m\.htm", href, re.I)
                    if match:
                        code = match.group(1)
                        href = f"{code}mc.gif"
                        map_large = urljoin(species["url"], href)
                    break
            if map_large:
                break

    # find all divs with recordings
    recording_blocks = soup.find_all(
        "div",
        class_=lambda x: x and "recording" in x
    )

    # loop through all the recordings found earlier
    for rec in recording_blocks:

        # extract the description from the previous recording block
        # the second recording is a clip of the first, so the description of the first provides
        # temperature and location for the second
        text = rec.get_text(" ", strip=True)

        if "recordingnopadding" in rec.get("class", []):
            prev_rec = rec.find_previous("div", class_="recording")

            if prev_rec:
                text = prev_rec.get_text(" ", strip=True)

        # extract audio file from the recording block
        audio = None
        audio_tag = rec.find("audio")
        if audio_tag:
            source = audio_tag.find("source", src=True)
            if source:
                audio = urljoin(species["url"], source["src"])

        # declare a spectrogram variable, initialized to "None" to prevent errors later
        spectrogram = None

        # loop through images in the recording block
        for img in rec.find_all("img", src=True):
            src = img["src"].lower()
            alt = (img.get("alt") or "").lower()

            combined = f"{src} {alt} {text.lower()}"

            # if the image is described as a spectrogram (or something similar), join the species url with the image source
            # and store it in the spectrogram variable
            if any(word in combined for word in [
                "spectrogram",
                "sonogram",
                "waveform",
                "graph",
                "graphed song"
            ]):
                spectrogram = urljoin(species["url"], img["src"])
                break

        # skip if nothing useful is found
        if not spectrogram:
            continue

        # attempt to extract temperature from description by searching for the "°" character
        temp = None
        if "°" in text:
            i = text.find("°")
            # remove any stray characters 
            temp = text[max(0, i - 5): i + 1].strip('abcdefghijklmnopqrstuvwxyz ')
            # encoding causes "Â" characters to show up before the "°", so remove those
            text = text.replace("Â", "")

        # attempt to extraction location from description using key words "from" and "in" that are usually found around the location
        loc = "No location found"

        if "from" in text:
            start = text.find("from") + 5
            end = text.find("°") if "°" in text else len(text)
            loc = text[start:end]

        elif "in" in text:
            start = text.find("in") + 3
            end = text.find("°") if "°" in text else len(text)
            loc = text[start:end]

        loc = loc.strip(" ,;.Â")

        # append all pieces of data to the grouped_data list as a dictionary
        katydid_grouped_data.append({
            "Species": species_name,
            "URL": species["url"],
            "Spectrogram": spectrogram,
            "Audio": audio,
            "Description": text,
            "Temperature": temp,
            "Location": loc,
            "Map": map_large
        })

    # courtesy pause so the SINA website doesn't get overwhelmed
    time.sleep(random.uniform(1, 2))


# In[134]:


# create a Pandas dataframe from the grouped_data list
katydid_df = pd.DataFrame(katydid_grouped_data)


# In[135]:


# rename the katydid_df columns
katydid_df.columns = ['Species', 'URL', 'Spectrogram', 'Audio_Link', 'Description', 'Temperature (°C)', 'Location', 'Map']


# In[ ]:


katydid_loc_list = []
for idx, row in katydid_df.iterrows():
    print(f"Current location: {row['Location']}")

    response = input("Type a replacement location: ").strip()

    if response:
        katydid_locations.append(response)
    else:
        katydid_locations.append(row['Location'])

print("Finished reviewing locations.")
katydid_loc_list


# In[139]:


katydid_df['Location'] = 'No location found',
'Franklin Co., Fla',
'Lawrence Co., Alabama',
'Tioga Co., N.Y.',
'McCracken Co., Ky',
'No location found',
'Jasper County, Texas',
'Alachua Co., Fla',
'Hancock County, Miss',
'Coper County, Mo',
'Chatham County, Ga.',
'Oswego County, N.Y.',
'Alachua County, Fla',
"St. John's County, Fla",
'Perry County, Miss',
'Alachua County, Fla',
'Chambers County, Texas',
'Marshall County, Okla',
'Franklin County, Fla',
'Hancock County, Miss',
'Sandoval County, N. Mex.',
'Wakulla County, Fla',
'Levy County, Fla',
'Schuyler County, N.Y.',
'Dade County, Fla',
'Clarke County, Miss',
'Shelby County, Ohio',
'Glades County, Fla',
'Limestone County, Texas',
'Charlton Co., Ga',
'Pima County, Ariz',
'Long Point, Lake Erie, Ontario, Canada',
'Alachua Co., Fla',
'Big Pine Key, Monroe Co, Fla',
'Charlotte Co, Fla',
'Plantation Key, Monroe Co, Fla',
'Chatham Co., Ga',
'Milot, Haiti, Wis',
'Ocean County, N.J.',
'Alachua Co., Fla',
'Livingston County, Michigan',
'Cape May Co., N.J.',
'Dade Co., Fla',
'Wakulla County, Fla',
'Hinds Co., Miss',
'Palm Beach Co., Fla',
'Obion County, Tenn',
'Alachua Co., Fla',
'Washington Co., Ohio',
'Alachua Co., Fla',
'Dade Co., Fla',
'Alachua Co., Fla',
'Murray Co., Ga',
'Tift Co., Ga',
'Leon Co., Fla',
'Terrebonne Par., La',
'Gwinnett Co., Ga',
'Marion Co., Fla',
'Howard Co., Tex',
'Kiowa Co., Okla',
'Brewster Co., Tex',
'Alachua Co., Fla',
'Brunswick Co., Va',
'Berkeley Co., Mo',
'Carter Co., Mo',
'Hidalgo Co., Tex',
'No location found',
'Berks Co., Pa',
'Alachua Co., Fla',
'No location found',
'No location found',
'Location found',
'No location found',
'Brewster Co., Tex',
'Alachua Co., Fla',
'Alachua Co., Fla',
'Attala Co., Miss',
'Attala Co., Miss',
'Pinna Co., Ariz',
'Alachua Co., Fla',
'Howard Co., Tex',
'Pecos Co., Tex',
'Alachua Co., Fla',
'Alachua Co., Fla',
'Alachua Co., Fla',
'Alachua Co., Fla',
'N.Y.',
'N.Y.',
'Escambia Co., Fla',
'Escambia Co., Fla',
'Los Angeles County, California',
'Los Angeles County, California',
'Livingston Co., Mich',
'Livingston Co., Mich',
'Livingston Co., Mich',
'Livingston Co., Mich',
'Livingston Co., Mich',
'Monroe Co., Fla',
'Monroe Co., Fla',
'Monroe Co., Fla',
'Brewster Co., Tex',
'Brewster Co., Tex',
'Kern County, California',
'No location found',
'Los Angeles County, California',
'No location found',
'Clark County, Nevada',
'No location found',
'Baja California, Mexico',
'No location found',
'Los Angeles County, California',
'No location found',
'Santa Barbara County, California',
'No location found',
'Ventura County, California',
'No location found',
'Los Angeles County, California',
'No location found',
'No location found',
'Malibu, Los Angeles County, California',
'Inyo County, California',
'No location found',
'Los Angeles Co., Calif. (Mescal Picnic Area)',
'San Bernardino County, California',
'No location found',
'Santa Barbara County, California',
'No location found',
'Baja California, Mexico',
'No location found',
'Inyo County, California',
'No location found',
'No location found',
'No location found',
'No location found',
'No location found',
'San Diego County, California',
'No location found',
'Ventura County, California',
'No location found',
'Los Angeles Co., Calif.',
'No location found',
'Inyo Co., Calif., 11 miles west of Lone Pine',
'Inyo Co., Calif., 6 miles west of Independence',
'Santa Barbara County, California',
'No location found',
'Lincoln County, Nevada',
'No location found',
'Baja California, Mexico',
'No location found',
'Nye County, Nevada',
'No location found',
'Riverside County, California',
'No location found',
'No location found',
'Moffat Co., Colo., near Dinosaur National Monument',
'Dyer Co., Tenn',
'Charlton Co., Ga',
'Clay Co., Fla',
'Levy Co., Fla',
'Dade Co., Fla',
'Dickson Co., Tenn',
'Schuyler Co, N.Y.',
'Mt. Diablo State Park, Contra Costa Co., Calif',
'Encinal Canyon, Santa Monica Mountains, Los Angeles Co., Calif',
'Brewster Co., Tex',
'Navajo Co., Ariz',
'Hobo Cpgr., Kern River Canyon, Kern Co., Calif',
'Hobo Cpgr., Kern River Canyon, Kern Co., Calif',
'Cochise Co., Ariz: Chiaricahua Mts.',
'Pima Co., Ariz.: Madera Canyon',
'Luna Co., N. Mex',
'Brewster Co., Tex',
'Luna Co., N. Mex',
'El Dorado Co., Calif',
"Los Angeles Co., Calif. (Devil's Punchbowl County Park)",
'Ventura Co., Calif. (Pont Mugu State Park)',
'Glenn Co., Calif., 6 mi w Plaskett Meadows',
'Mono Co., Calif.',
'No location found',
'No location found',
'No location found',
'No location found',
'No location found',
'No location found',
'No location found',
'No location found',
'No location found',
'No location found',
'No location found',
'No location found',
'No location found',
'No location found',
'No location found',
'No location found',
'No location found',
'No location found',
'No location found',
'Calhoun County, Tex',
'Freestone County, Tex',
'Webb County, Tex',
'Navajo County, Ariz',
'Mineral County, Nev. (Weber Reservoir)',
'Brewster Co., Tex']


# In[141]:


# save cricket_df using IPython magic
get_ipython().run_line_magic('store', 'katydid_df')


# ## Frog Dataframe

# In[63]:


# This cell interacts with the Xeno-Canto API to retrieve all its frog call data. It loops over all the frog call pages
# and extracts all the data stored there.

page_num = 1
base_url = f'https://xeno-canto.org/api/3/recordings?query=grp:frogs&page={page_num}&key=18a98cdc0e5e1df2c91e00a17f4bfcf89cd501b6' # use an individual Xeno-Canto API key
recordings = []

# use the requests library to get data from the first page of the API endpoint
response = requests.get(base_url)
data = response.json()
recordings.extend(data["recordings"])

# loop through all the remaining pages and use the requests library to get data from them
for n in range(2,58):
    page_num = n
    base_url = base_url = f'https://xeno-canto.org/api/3/recordings?query=grp:frogs&page={page_num}&key=18a98cdc0e5e1df2c91e00a17f4bfcf89cd501b6'
    response = requests.get(base_url)
    data = response.json()
    recordings.extend(data["recordings"])

    # courtesy pause so the API doesn't get overwhelmed
    time.sleep(random.uniform(2,4))


# In[64]:


# flatten nested data
df = pd.json_normalize(recordings)


# In[65]:


# extract useful columns
frog_df = df[['gen', 'sp', 'cnt', 'loc', 'lat', 'lon', 'type', 'file', 'sono.med']]


# In[66]:


# rename extracted columns for readability
frog_df.columns = ['Genus', 'Species', 'Country', 'Location', 'Latitude', 'Longitude', 'Call Type', 'File', 'Spectrogram']


# In[142]:


get_ipython().run_line_magic('store', 'frog_df')


# ## Downloading Files

# ### Crickets

# In[49]:


# get_file_id is a helper function that extracts the file name (without its extension) from a URl

def get_file_id(url):
    return os.path.splitext(os.path.basename(str(url)))[0]


# In[51]:


# define the base_folder where all the files will be stored
base_folder = Path.home() / "Discrete_Signals"

# create a dictionary of species folders, all stored under the base folder "Discrete_Signals"
group_folders = {
    "crickets": base_folder / "Crickets",
    "katydids": base_folder / "Katydids",
    "frogs": base_folder / "Frogs"
}

# loop over group_folders to create all the species folders
for folder in group_folders.values():
    folder.mkdir(parents=True, exist_ok=True)


# In[52]:


# download_file is a helper function that safely downloads urls

def download_file(url, path, headers):
    '''Downloads a file from a URL and saves it locally. Prevents HTML error pages from being downloaded instead of
    images or audio files.'''
    try:
        # request the file
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()

        # check the content type returned by the server
        content_type = r.headers.get("Content-Type", "").lower()

        # if a file that is an HTML page is found, skip it, print a message, and return nothing
        if "text/html" in content_type:
            print(f"Skipping HTML page masquerading as asset: {url}")
            return

        # check if the file is an error message
        if r.content.startswith(b"<!DOCTYPE") or r.content.startswith(b"<html"):
            print(f"Skipping text/html payload for: {url}")
            return

        # save the downloaded file
        with open(path, "wb") as f:
            f.write(r.content)

    # print an error message and the exception if the download fails
    except Exception as e:
        print(f"Download failed: {url}")
        print(e)


# In[ ]:


# This cell loops through all the species in cricket_df, retrieves the links to the spectrograms, audio files, and range maps,
# creates a subfolder under Discrete_Signals / Crickets for each of the species, and downloads the spectrograms, audio files,
# and range maps to that subfolder using download_file

# loop through the Pandas dataframe row by row
for idx, row in cricket_df.iterrows():
    # get the urls from the Spectrogram, Audio_Link, and Map columns
    spectrogram_url = row.get("Spectrogram")
    audio_url = row.get("Audio_Link")
    map_url = row.get("Map")

    # if there are no values in the Spectrogram, Audio_Link, and Map columns, continue to prevent an error
    if pd.isna(spectrogram_url) and pd.isna(audio_url) and pd.isna(map_url):
        continue

    # create species subfolder, named Genus_species, inside Crickets
    species = str(row["Species"]).replace(" ", "_")
    species_folder = group_folders["crickets"] / species
    species_folder.mkdir(parents=True, exist_ok=True)

    # Declare a spec_id variable that will store the file ID of each spectrogram, in case a species has multiple spectrograms
    # on their page. This prevents any spectrograms from being overwritten.
    spec_id = None

    # check if the spectrogram URL exists and give it a .gif extension if it doesn't have an image extension
    if pd.notna(spectrogram_url) and spectrogram_url:
        ext = os.path.splitext(spectrogram_url)[1].lower()
        if ext not in [".jpg", ".jpeg", ".png", ".gif", ".webp"]:
            ext = ".gif"

        # call get_file_id to assign the spectrogram an ID, and use download_file to download the spectrogram to
        # the species subfolder
        spec_id = get_file_id(spectrogram_url)
        spec_path = species_folder / f"{species}_spectrogram_{spec_id}{ext}"
        download_file(spectrogram_url, spec_path, headers)

    # check if the audio URL exists and give it a .wav extension if it doesn't have an audio extension
    if pd.notna(audio_url):
        audio_url = str(audio_url).strip()
        ext = os.path.splitext(audio_url)[1].lower()
        if ext not in [".mp3", ".wav", ".ogg"]:
            ext = ".wav"

        # define an ID for the audio file using either the spectrogram ID or the get_file_id function
        audio_id = spec_id or get_file_id(audio_url)
        audio_path = species_folder / f"{species}_audio_{audio_id}{ext}"

        # try to save the audio file to the species subfolder, and print an error message if it is unsuccessful
        try:
            r = session.get(audio_url, timeout=20)
            r.raise_for_status()

            with open(audio_path, "wb") as f:
                f.write(r.content)

        except Exception as e:
            print(f"Error downloading audio {audio_url}")
            print(e)

    # check if the range map URL exists and give it a .gif extension if it doesn't have an image extension
    if pd.notna(map_url) and map_url:
        ext = os.path.splitext(map_url)[1].lower()
        if ext not in [".gif", ".jpg", ".jpeg", ".png", ".webp"]:
            ext = ".gif"

        # use get_file_id to get an ID for the map and download it to the species subfolder
        map_id = get_file_id(map_url)
        map_path = species_folder / f"{species}_map_{map_id}{ext}"
        download_file(map_url, map_path, headers)


# ### Katydids

# In[ ]:


# This cell loops through all the species in katydid_df, retrieves the links to the spectrograms, audio files, and range maps,
# creates a subfolder under Discrete_Signals / Katydids for each of the species, and downloads the spectrograms, audio files,
# and range maps to that subfolder using download_file

# loop through the Pandas dataframe row by row
for idx, row in katydid_df.iterrows():
    # get the urls from the Spectrogram, Audio_Link, and Map columns
    spectrogram_url = row.get("Spectrogram")
    audio_url = row.get("Audio_Link")
    map_url = row.get("Map")

    # if there are no values in the Spectrogram, Audio_Link, and Map columns, continue to prevent an error
    if pd.isna(spectrogram_url) and pd.isna(audio_url) and pd.isna(map_url):
        continue

    # create species subfolder, named Genus_species, inside Katydids
    species = str(row["Species"]).replace(" ", "_")
    species_folder = group_folders["katydids"] / species
    species_folder.mkdir(parents=True, exist_ok=True)

    # Declare a spec_id variable that will store the file ID of each spectrogram, in case a species has multiple spectrograms
    # on their page. This prevents any spectrograms from being overwritten.
    spec_id = None

    # check if the spectrogram URL exists and give it a .gif extension if it doesn't have an image extension
    if pd.notna(spectrogram_url) and spectrogram_url:
        ext = os.path.splitext(spectrogram_url)[1].lower()
        if ext not in [".jpg", ".jpeg", ".png", ".gif", ".webp"]:
            ext = ".gif"

        # call get_file_id to assign the spectrogram an ID, and use download_file to download the spectrogram to
        # the species subfolder
        spec_id = get_file_id(spectrogram_url)
        spec_path = species_folder / f"{species}_spectrogram_{spec_id}{ext}"
        download_file(spectrogram_url, spec_path, headers)

    # check if the audio URL exists and give it a .wav extension if it doesn't have an audio extension
    if pd.notna(audio_url):
        audio_url = str(audio_url).strip()
        ext = os.path.splitext(audio_url)[1].lower()
        if ext not in [".mp3", ".wav", ".ogg"]:
            ext = ".wav"

        # define an ID for the audio file using either the spectrogram ID or the get_file_id function
        audio_id = spec_id or get_file_id(audio_url)
        audio_path = species_folder / f"{species}_audio_{audio_id}{ext}"

        # try to save the audio file to the species subfolder, and print an error message if it is unsuccessful
        try:
            r = session.get(audio_url, timeout=20)
            r.raise_for_status()

            with open(audio_path, "wb") as f:
                f.write(r.content)

        except Exception as e:
            print(f"Error downloading audio {audio_url}")
            print(e)

    # check if the range map URL exists and give it a .gif extension if it doesn't have an image extension
    if pd.notna(map_url) and map_url:
        ext = os.path.splitext(map_url)[1].lower()
        if ext not in [".gif", ".jpg", ".jpeg", ".png", ".webp"]:
            ext = ".gif"

        # use get_file_id to get an ID for the map and download it to the species subfolder
        map_id = get_file_id(map_url)
        map_path = species_folder / f"{species}_map_{map_id}{ext}"
        download_file(map_url, map_path, headers)


# ### Frogs

# In[68]:


def download_frogs(frog_df, base_folder, headers):
    '''Downloads the frog audio files straight from frog_df, saving them to species-specific subfolders
    located under Discrete_Signals / Frogs.'''

    # creates the Frogs folder used to store all the data
    frog_root = base_folder / "Frogs"

    # create a stateful session object
    session = requests.Session()
    session.headers.update(headers)

    total = len(frog_df)

    # loop through all the recordings in the dataframe and extract the genus, species, and audio link
    for n, (idx, row) in enumerate(frog_df.iterrows(), start=1):

        genus = str(row["Genus"])
        species = str(row["Species"]).strip("'")
        species_name = f"{genus}_{species}"

        audio_url = row.get("File")

        # skip rows without audio
        if pd.isna(audio_url):
            continue

        # create species folder
        species_folder = frog_root / species_name
        species_folder.mkdir(parents = True, exist_ok = True)

        # determine file extension
        ext = os.path.splitext(str(audio_url))[1].lower()
        if ext not in [".mp3", ".wav", ".ogg"]:
            ext = ".mp3"

        # count existing audio files and assign next number
        existing = list(species_folder.glob(f"{species}_audio_*"))
        audio_num = len(existing) + 1

        audio_path = species_folder / f"{species}_audio_{audio_num}{ext}"

        try:
            # download the audio file and save it locally
            r = session.get(audio_url, timeout=20)

            if r.status_code == 200:
                with open(audio_path, "wb") as f:
                    f.write(r.content)

                print(f"Saved: {audio_path.name}")

            else:
                print(f"Audio failed ({r.status_code}): {audio_url}")

        # print an error message if unable to download
        except Exception as e:
            print(f"Error downloading audio: {audio_url}")
            print(e)

        print(f"{species_name} downloaded, {n*100/total}% complete")

        # courtesy pause
        time.sleep(random.uniform(1, 2))


# In[ ]:


download_frogs(frog_df, base_folder, headers)

