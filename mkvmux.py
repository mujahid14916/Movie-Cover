import os
import stat
import re
import requests
import argparse
import logging
import subprocess
from pymkv import MKVFile, MKVAttachment, MKVTrack
from string import punctuation
from google_images_search import GoogleImagesSearch
from PIL import Image
from urllib.request import urlopen


log_path = os.path.join(os.path.dirname(__file__), 'debug.log')
logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s] [%(levelname)s] - %(message)s",
    handlers=[
        logging.FileHandler(log_path),
        logging.StreamHandler()
    ]
)

POSTER_DIR = os.path.join(os.path.dirname(__file__), 'movie_posters')
MOVIE_NAME_FORMAT = '{name}-{year}.{ext}'
VALID_VIDEO_FORMAT = ['mkv', 'mp4', 'avi']
GIS = GoogleImagesSearch('AIzaSyD_hdrVUehVEw9aaHzAhXqprk1LTUlJq9o', 'ab72f683c4302c915')


def make_get_request(url):
    """Make Get Request

    Args:
        url (str): URL for GET request

    Returns:
        tuple: Status Code, Response Content
    """
    response = requests.get(url)
    return response.status_code, response.content


def get_poster_filename(movie_name, movie_year, ext='jpg'):
    """Return standard poster file format

    Args:
        movie_name (str): Movie Name
        movie_year (str): Movie Year
        ext (str, optional): Image extension. Defaults to 'jpg'.

    Returns:
        str: Standard poster file name
    """
    return MOVIE_NAME_FORMAT.format(
        name=movie_name.replace(' ', '-'), 
        year=movie_year, 
        ext=ext
    )


def download_poster_from_dvdreleasedates(movie_name, movie_year):
    """Download Movie Poster from DvdReleaseDates.com website

    Args:
        movie_name (str): Movie Name
        movie_year (str): Movie Year

    Returns:
        str: Downloaded Image Path
    """
    logging.info("Query from DvdReleaseDates")
    url = 'https://www.dvdsreleasedates.com/posters/800/{movie_letter}/{movie_name}-movie-poster.jpg'
    movie_letter = 0 if movie_name[0].isdigit() else movie_name[0]
    movie_name = movie_name.replace(' ', '-')
    movie_name = ' '.join(movie_name.split())
    movie_name = '-'.join(movie_name.split('-'))
    formatted_url = url.format(movie_letter=movie_letter, movie_name=movie_name+'-'+movie_year)
    code, content = make_get_request(formatted_url)
    if code != 200:
        formatted_url = url.format(movie_letter=movie_letter, movie_name=movie_name)
        code, content = make_get_request(formatted_url)
    if code == 200:
        poster_name = get_poster_filename(movie_name, movie_year)
        poster_path = os.path.join(POSTER_DIR, poster_name)
        with open(poster_path, 'wb') as f:
            f.write(content)
        return poster_path


def download_poster_from_google_api(movie_name, movie_year):
    """Download Movie Poster from Google Image API Search

    Args:
        movie_name (str): Movie Name
        movie_year (str): Movie Year

    Returns:
        str: Downloaded Image Path
    """
    logging.info("Query from Google API")
    search_queries = [
        '{movie_name} {movie_year} movie hd poster',
        '{movie_name} {movie_year} cover hd poster',
        '{movie_name} {movie_year} hd poster',
        '{movie_name} {movie_year} poster',
        '{movie_name} {movie_year} cover',
    ]
    google_search_params = {
        'num': 10,
        'fileType': 'jpg',
        'imgSize': 'XXLARGE',
    }
    for query in search_queries:
        try:
            google_search_params['q'] = query.format(movie_name=movie_name, movie_year=movie_year)
            GIS.search(search_params=google_search_params)
            break
        except:
            continue
    for image in GIS.results():
        try:
            img = Image.open(urlopen(image.url))
        except Exception:
            continue
        w, h = img.size
        if h > 1.4*w and h >= 900:
            poster_name = get_poster_filename(movie_name, movie_year)
            poster_path = os.path.join(POSTER_DIR, poster_name)
            img.save(poster_path)
            return poster_path


def download_poster(movie_name, movie_year):
    """Downloads Movie Poster for the Movie

    Args:
        movie_name (str): Movie Name
        movie_year (str): Movie Year

    Raises:
        NotImplementedError: Raises exception if the current implementation fails

    Returns:
        str: Downloaded Image Path
    """
    methods = [
        download_poster_from_dvdreleasedates,
        download_poster_from_google_api
    ]
    poster_path = None
    for method in methods:
        poster_path = method(movie_name, movie_year)
        if poster_path is not None:
            return poster_path
    raise NotImplementedError(download_poster.__name__ + '() full implementation pending')


def get_movie_cover(movie_name, movie_year):
    """Get Movie Poster for Movie from local system or download if not found

    Args:
        movie_name (str): Movie Name
        movie_year (str): Movie Year

    Returns:
        str: Movie Poster Path
    """
    if not os.path.isdir(POSTER_DIR):
        os.mkdir(POSTER_DIR)
    supported_ext = ['jpg', 'png', 'jpeg']
    poster_found = False

    # Search existing poster: could be custom movie poster
    for ext in supported_ext:
        poster_path = os.path.join(POSTER_DIR, get_poster_filename(movie_name, movie_year, ext=ext))
        if os.path.isfile(poster_path):
            poster_found = True
            break

    if poster_found:
        return poster_path
    else:
        return download_poster(movie_name, movie_year)


def get_movie_name_and_year(movie_file):
    """Parse movie name and year from movie file name

    Args:
        movie_file (str): Video File Name 

    Raises:
        ValueError: Raises Exception if file name doesnot contain name and year

    Returns:
        tuple: Movie Name, Movie Year
    """
    file_name = movie_file.replace('\\', '/').split('/')[-1]
    year_pattern1 = re.compile(r'\(\d{4}\)')
    year_pattern2 = re.compile(r'\d{4}')
    matched = re.search(year_pattern1, file_name)
    year_start_idx = None
    if matched:
        year_start_idx = matched.start()+1
        year_end_idx = matched.end()-1
    else:
        matched = re.search(year_pattern2, file_name)
        if matched:
            year_start_idx = matched.start()
            year_end_idx = matched.end()
    if year_start_idx:
        movie_year = file_name[year_start_idx:year_end_idx]
        movie_title = file_name[:year_start_idx]
        movie_title = movie_title.replace('.', ' ')
        movie_title = movie_title.translate(str.maketrans(' ', ' ', punctuation.replace('-', '')))
        movie_title = movie_title.replace('-', ' ')
        movie_title = ' '.join(movie_title.split())
        return movie_title, movie_year
    else:
        raise ValueError("Invalid movie name format. Use MOVIE_NAME-(YEAR).EXT naming format.")


def movie_poster_added(movie_file):
    """Check if the Movie file contains poster

    Args:
        movie_file (str): Movie File Path

    Returns:
        bool: Returns true if exists
    """
    cmd = 'mkvmerge --identify "{}"'.format(movie_file)
    output = subprocess.check_output(cmd, shell=True).decode('utf-8').split('\n')
    for line in output:
        if line.startswith('Attachment ID') and "'cover.jpg'" in line:
            return True
    return False


def mux_movie(movie_file, cover_file):
    """Generate MKV file with added movie poster

    Args:
        movie_file (str): Movie File Path
        cover_file (str): Image File Path
    """
    full_file_name = movie_file.replace('\\', '/').split('/')[-1]
    file_name = '.'.join(full_file_name.split('.')[:-1])
    file_directory = os.path.dirname(movie_file)
    temp_file_name = 'temp_' + file_name
    temp_file_path = os.path.join(file_directory, temp_file_name + '.mkv')
    if movie_file.endswith('.mkv'):
        mkv = MKVFile(movie_file)
    else:
        mkv = MKVFile()
        i = 0
        while True:
            try:
                mkv.add_track(MKVTrack(movie_file, track_id=i))
                i += 1
            except:
                break
    mkv.title = file_name
    attachment = MKVAttachment(cover_file, name='cover.jpg')
    mkv.no_attachments()
    mkv.add_attachment(attachment)
    mkv.mux(temp_file_path, silent=True)
    os.chmod(movie_file, stat.S_IWRITE)
    os.remove(movie_file)
    os.rename(temp_file_path, os.path.join(file_directory, file_name + '.mkv'))


def update_movie_cover(movie_file, cover_file=None):
    """Update Movie Cover

    Args:
        movie_file (str): Movie File Path
        cover_file (str, optional): Image File Path. Defaults to None.
    """
    if cover_file is None:
        movie_name, movie_year = get_movie_name_and_year(movie_file)
        cover_file = get_movie_cover(movie_name, movie_year)
    mux_movie(movie_file, cover_file)


def update_file(directory, file, force=False):
    """Update a Movie File to add movie poster

    Args:
        directory (str): Movie Directory Path
        file (str): Movie File Name
        force (bool): Force Update Movie Poster. Defaults to False.
    """
    try:
        movie_name, movie_year = get_movie_name_and_year(file)
        movie_file = os.path.join(directory, file)
        logging.info(movie_file)
        logging.info("{} [{}]".format(movie_name, movie_year))
        if not movie_poster_added(movie_file) or force:
            logging.info("Adding Movie Cover")
            update_movie_cover(movie_file)
        else:
            logging.info("Skipping...")
    except Exception as e:
        logging.error("Failed: {}, Reason: {}".format(file, e))


def traverse_movies_directory(directory, parent_dir='', force=False):
    """Recursively Update Movie cover for passed directory

    Args:
        directory (str): Movies Root directory
        parent_dir (str, optional): Used internally to keep track of parent directory. Defaults to ''.
        force (bool, optional): Force Update Movie Poster. Defaults to False.
    """
    current_dir = directory.replace('\\', '/').split('/')[-1]
    files = os.listdir(directory)
    # root_dir = '{}{}'.format(parent_dir, current_dir)
    # if not os.path.isdir(root_dir):
    #     os.mkdir(root_dir)
    for file in files:
        file_path = '{}/{}'.format(directory, file)
        if os.path.isdir(file_path):
            traverse_movies_directory(directory=file_path, parent_dir=parent_dir+current_dir+'/', force=force)
        if not any(file.endswith(item) for item in VALID_VIDEO_FORMAT) or 'sample' in file.lower():
            continue
        update_file(directory, file, force=force)


def main():
    """Main function to initiate execution
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-m', '--movies_directory', type=str, help='movies directory/file path', required=True)
    parser.add_argument('-f', '--force', action='store_true', help='force update')
    args = parser.parse_args()
    path = args.movies_directory
    force = args.force
    logging.info("Command line args:")
    logging.info("\tPath: {}".format(path))
    logging.info("\tForce Update: {}".format(force))
    if os.path.isdir(path):
        try:
            traverse_movies_directory(directory=path, force=force)
        except Exception as e:
            logging.info("Movies Update failed: {}".format(e))
    else:
        directory = os.path.dirname(path)
        file = path.replace('\\', '/').split('/')[-1]
        update_file(directory, file, force=force)


if __name__ == '__main__':
    main()