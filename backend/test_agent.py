
from agent import extract_search_details, detect_domains

queries = [
    "Find AI/ML fresher jobs all over India",
    "Find machine learning internships in India",
    "Find Python developer jobs in India",
    "Find Generative AI internships in India",
    "Find full stack developer jobs in India",
]

for query in queries:
    keywords, location = extract_search_details(query)

    print("\nQuery:", query)
    print("Detected domains:", detect_domains(query))
    print("Search keywords:", keywords)
    print("Location:", location)
