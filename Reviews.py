#!/usr/bin/env python

# import needed libraries
from Tools import SafeThread, write_books, read_books
from bs4 import BeautifulSoup
from langdetect import detect
from Browser import Browser
from Writer import Writer


# A class to Scrape books Reviews from GoodReads.com
class Reviews:
    def __init__(self, lang="ar"):
        # Language of reviews to be scraped
        self.lang = lang
        # Browsing and writing managers
        self.br = Browser()
        self.wr = Writer()
        # Counter for reviews from different languages
        self._invalid = None

    # Scrape and write books' reviews to separate files
    def output_books_reviews(self, books_ids, consider_previous=True):
        if consider_previous:
            # Don't loop through already scraped books
            self.wr.consider_written_files(books_ids)
        # Show how many books are going to be scraped
        print(f"Scraping {len(books_ids)} Books")
        # Loop through book ids in array and scrape books
        for book_id in books_ids:
            try:
                self.output_book_reviews(book_id)
            except NameError as new_id:
                ids = read_books()
                ids[ids.index(book_id)] = new_id.args[0]
                write_books(ids)
                self.wr.delete_file()
                raise ConnectionError("Failed to redirect to book URL")
            except Exception:
                pass

    # Scrape and write one book's reviews to a file
    def output_book_reviews(self, book_id):
        # Open book file and page by its Id
        self.wr.open_book_file(book_id)
        self.br.open_book_page(book_id)
        # Reset invalid reviews counter and page counter
        self._invalid = 0
        # Scrape book meta data in first line
        self.run(self._scrape_book_meta, [book_id])
        # Scrape first page of the book anyway
        self.run(self._scrape_book_reviews)
        no_next_page = False
        # Scrape the remaining pages
        while self._invalid < 60:
            # Go to next page if there's one
            if no_next_page or not self.br.goto_next_page():
                no_next_page = False
                # Switch to a different reviews mode
                if not self.br.switch_reviews_mode(book_id):
                    # Break after switching to all modes
                    break
            # Wait until requested book reviews are loaded
            if self.br.are_reviews_loaded():
                # Scrape loaded book reviews
                self.run(self._scrape_book_reviews)
            else:
                no_next_page = True
        # Finalize file name and close it
        self.wr.close_book_file()

    # Scrape and write book and author data
    def _scrape_book_meta(self, html, book_id):
        # Create soup object from page html
        soup = BeautifulSoup(html, "lxml")
        # Store book meta section of the page in soup unless book not available
        soup = soup.find(id="metacol") or soup.find(class_="errorBox").get_text().strip()
        # If book is not found
        if soup == "Could not find this book.":
            print(f"*Book ID:\t{book_id:<15}Not Found!")
            # Close file and raise an error
            self.wr.close_book_file()
            raise FileNotFoundError
        # Get book title and remove spaces from it
        title = soup.find(id="bookTitle").get_text(". ", strip=True)
        # Get average rating of the book out of five
        rating = soup.find(class_="average").get_text()
        # Store author data section
        author = soup.find(class_="authorName")
        # Get author id from url
        id_ = author.get("href")[38:].split(".")[0]
        # Get author name
        name = author.find().get_text()
        # Write scraped meta data to file's first line
        self.wr.write_book_meta(book_id, title, rating, id_, name)
        # Display book id and title
        print(f"*Book ID:\t{book_id:<15}Title:\t{title}")

    # Scrape a single page's reviews
    def _scrape_book_reviews(self, html):
        # Store reviews section of the page in soup
        soup = BeautifulSoup(html, "lxml").find(id="bookReviews")
        # Loop through reviews individually
        for review in soup.find_all(class_="review"):
            try:  # Get user / reviewer id
                user_id = review.find(class_="user").get("href")[11:].split("-")[0]
                # Get rating out of five stars
                stars = len(review.find(class_="staticStars").find_all(class_="p10"))
                # Get full review text even the hidden parts, and remove spaces and newlines
                comment = review.find(class_="readable").find_all("span")[-1].get_text(". ", strip=True)
                # Detect which language the review is in
                if detect(comment) != self.lang:
                    # Count it as a different language review
                    self._invalid += 1
                    continue
                # Get review date
                date = review.find(class_="reviewDate").get_text()
            # Skip the rest if one of the above is missing
            except Exception:
                # Count it as an invalid review
                self._invalid += 2
                continue
            # If it's not a strike, reset the counter
            self._invalid = 0
            # Get review ID
            review_id = review.get("id")[7:]
            # Write the scraped review to the file
            self.wr.write_review(review_id, user_id, date, stars, comment)
            # Add review id to ids
            print(f"Added ID:\t{review_id}")
        return True

    # Starts a scraping process on a new thread
    def run(self, method, args=[]):
        SafeThread(target=method, args=[self.br.page_source] + args).start()

    def close(self):
        self.br.close()
        self.wr.close()
        print("Closed Reviews")
