"""Static site configuration + Jinja2 templates — shared module.
Kept out of main.py to avoid import cycles (routes and app both need it)."""
import os

from fastapi.templating import Jinja2Templates

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SITE_CONFIG = {
    "name": "INFRASURE 2027",
    "short_title": "INFRASURE 2027",
    "tagline": "International Conference on Infrastructure Sustainability and Resilience Forum",
    "dates": "22 – 24 January 2027",
    "venue": "Rajarhat Extension Centre, IIT Kharagpur, Kolkata",
    "organizer": "Department of Civil Engineering, IIT Kharagpur",
    "jubilee": "Platinum Jubilee Celebrations of IIT Kharagpur (est. 1951)",
    "convener": "Prof. Manish Pandey",
    "email": "infrasure2027@civil.iitkgp.ac.in",
    "domain": "Sustainable Development",
    "about_headline": (
        "A high-energy, idea-driven forum where science meets practice, "
        "technology meets policy, and innovation meets responsibility."
    ),
    "about_iitkgp": {
        "eyebrow": "About IIT Kharagpur",
        "title": "Dedicated to the service of the Nation",
        "motto_sanskrit": "योगः कर्मसु कौशलम्",
        "motto_translation": "Excellence in action is Yoga",
        "motto_source": "Bhagavad Gita — Sri Krishna's discourse with Arjuna",
        "text": (
            "IIT Kharagpur, established in 1951, is the first and largest of the IITs. "
            "Its motto \"योगः कर्मसु कौशलम्\" — \"Excellence in action is Yoga\" — urges "
            "equanimity and focus on the task before us, the source of perfection in "
            "endeavour that leads to service of the Nation."
        ),
        "motto_detail": (
            "In the larger context of the Gita, the quote urges man to acquire equanimity "
            "because a mind of equanimity allows a man to shed distracting thoughts of the "
            "effects of his deeds and concentrate on the task before him. Equanimity is the "
            "source of perfection in Karmic endeavours that leads to Salvation."
        ),
        "image": "/media/iitkgp.JPG",
        "image_alt": "IIT Kharagpur main building",
    },
    "about_civil": {
        "eyebrow": "About the Host Department",
        "title": "Department of Civil Engineering, IIT Kharagpur",
        "subtitle": "One of the oldest Departments in the Institute — since 1951",
        "text": (
            "The Civil Engineering department is one of the oldest Departments in the "
            "Institute with its beginning in 1951. The department has been involved in "
            "areas of Soil Mechanics, Transportation Engineering, Hydraulics and Structures "
            "and Environmental Engineering."
        ),
        "text2": (
            "Sponsored and consultancy projects undertaken by the department include Disaster "
            "Mitigation & Management, Analysis, Evaluation and Design of Highway and Airport "
            "pavements, Non-destructive Evaluation and Restoration of various structures such "
            "as buildings and bridges, Process Modifications for pollution mitigation, Ground "
            "Improvement and Sediment Transport and Scour studies."
        ),
        "image": "/media/civildept.png",
        "image_alt": "Department of Civil Engineering, IIT Kharagpur",
    },
    "about_text": (
        "Climate change, rapid urbanization, population growth, and increasing pressure on "
        "natural resources are creating unprecedented challenges for civil infrastructure and "
        "water systems worldwide. INFRASURE 2027 brings together thinkers and doers committed "
        "to shaping a sustainable and climate-resilient future through Civil and Water "
        "Resources Engineering — at local, regional, and global scales."
    ),
    "pillars": [
        {
            "title": "Sustainable",
            "text": "Infrastructure that meets today's needs without compromising tomorrow — resource efficiency and net zero at the core.",
        },
        {
            "title": "Resilient",
            "text": "Systems built to withstand floods, droughts, and extreme weather events through climate-adaptive design.",
        },
        {
            "title": "Nature-based Solutions",
            "text": "River restoration, green infrastructure, groundwater recharge, and ecosystem conservation as real solutions.",
        },
    ],
    "objectives": [
        "Provide a forum for cutting-edge research and innovations in sustainable civil and water engineering.",
        "Promote the development of climate-resilient infrastructure capable of withstanding extreme weather events, floods, droughts, and climate-related risks.",
        "Explore innovative technologies, digital tools, artificial intelligence, and smart monitoring systems for sustainable infrastructure and water resource management.",
        "Promote multidisciplinary research for nature-based solutions, net zero, flood management, river restoration, groundwater recharge, and ecosystem conservation.",
        "Encourage early-career researchers and students through dedicated sessions, mentoring, and awards.",
        "Strengthen collaboration among academia, government agencies, industries, and international organizations.",
    ],
    "key_facts": [
        {"value": "3", "label": "Conference Days"},
        {"value": "9", "label": "Core Themes"},
        {"value": "6", "label": "Key Objectives"},
        {"value": "22–24 Jan", "label": "Dates, 2027"},
    ],
    "themes": [
        {
            "label": "Theme 1",
            "name": "Environmental Monitoring and Management",
            "topics": [
                "Clean Air Strategies: Monitoring and Management",
                "Water and Wastewater Management",
                "Solid & Hazardous Waste Management",
                "Circular Economy and Sustainability",
                "Life Cycle Assessment (LCA)",
                "Thermal and Visual Comfort",
                "Noise Pollution Control",
            ],
        },
        {
            "label": "Theme 2",
            "name": "Geohazards and Geotechnical Infrastructure",
            "topics": [
                "Ground Improvement and Stabilization Techniques",
                "Foundations and Earthworks",
                "Geosynthetics and Geocomposites",
                "Slope Stability",
                "Geoenvironmental Engineering",
                "Offshore Geotechnics",
                "Earth Retaining Structures",
                "Pavement Geotechnics",
                "Earthquake Geotechnical Engineering",
                "Geohazard Risk Assessment and Management",
                "Tunnelling and Underground Construction",
                "Thermal–Hydro–Mechanical Behaviour of Geomaterials",
            ],
        },
        {
            "label": "Theme 3",
            "name": "Hydraulic and Hydrologic Systems",
            "topics": [
                "Climate Change Impacts on Water Resources Systems",
                "Flood and Drought Risk Assessment, Forecasting and Management",
                "Urban Flooding and Stormwater Management",
                "Watershed Management",
                "Groundwater Hydrology",
                "Smart Water Networks and Pipe Hydraulics",
                "Experimental Hydraulics",
                "Riverbank Protection, Sediment Dynamics, and Morphological Resilience",
                "Dam Safety",
                "Computational Methods in Hydraulic and Hydrologic Systems",
            ],
        },
        {
            "label": "Theme 4",
            "name": "Infrastructure Design and Innovation",
            "topics": [
                "Sustainable Housing and Green Buildings",
                "Analysis and Design of Structural Systems",
                "Structural Dynamics and Earthquake Engineering",
                "Experimental studies in Structural Engineering",
                "Computational Methods in Infrastructure Systems",
            ],
        },
        {
            "label": "Theme 5",
            "name": "Pavement, Traffic and Transportation Technologies",
            "topics": [
                "Pavement Engineering and Technologies",
                "Traffic Engineering and Management",
                "Smart Cities and Urban Mobility",
                "Intelligent Transportation Systems",
                "Sustainable and Resilient Transportation Systems",
            ],
        },
        {
            "label": "Theme 6",
            "name": "Surveying and Geoinformatics",
            "topics": [
                "Remote Sensing, GIS, UAVs, and Geospatial Analytics",
                "Urban Planning and Land Use Management",
                "Mapping of Urban Infrastructure",
            ],
        },
        {
            "label": "Theme 7",
            "name": "Future Ready Construction Materials and Technologies",
            "topics": [
                "Bio-Based, Natural Fiber, Eco-Friendly, and Recycled Construction Materials",
                "Circular Economy Approaches in Construction",
                "Modular and Prefabricated Construction",
                "Robotics and Automation in Construction",
                "Life Cycle Assessment (LCA) for construction",
            ],
        },
        {
            "label": "Theme 8",
            "name": "Digital Twin, Instrumentation and AI/ML in Civil Engineering",
            "topics": [
                "Building Information Modelling (BIM) and Digital Twin Technologies",
                "IoT, Smart Sensors, and Real-Time Infrastructure Monitoring",
                "Digital Twin and AI/ML for Environmental Monitoring and Management; Geohazards and Geotechnical Infrastructure; Hydraulic and Hydrologic Systems; Infrastructure Design and Maintenance; Traffic and Pavement Technologies",
                "Big Data, Cloud Computing, and Decision Support Systems",
            ],
        },
        {
            "label": "Theme 9",
            "name": "Energy Recovery",
            "topics": [
                "Geothermal Energy",
                "Hydropower Energy",
                "Waste to Energy",
                "Tidal Energy",
                "Offshore Wind Turbine",
            ],
        },
    ],
    "format_points": [
        "Inaugural and valedictory sessions",
        "Keynote and plenary lectures by eminent national and international experts",
        "Thematic technical sessions — oral and poster presentations",
        "Panel discussions and roundtables on policy and practice",
        "Special sessions and workshops on emerging tools and methodologies",
        "Smart IITKGP hackathon",
        "Student and early-career researcher forums",
        "Industry and technology showcase",
    ],
    "participants": [
        "Researchers and academicians in water and environmental disciplines",
        "Engineers and consultants",
        "Policymakers and government officials",
        "Industry professionals and technology providers",
        "Non-governmental organizations and development agencies",
        "Research scholars, undergraduate & postgraduate students",
    ],
    "publications": [
        "Conference proceedings with ISBN",
        "Springer book series",
        "Special issues in indexed national or international journals (subject to journal guidelines)",
    ],
    "submit_rules": [
        "Submit a PPT or a Poster presentation",
        "Up to 2 submissions per student — any combination of PPT and Poster",
        "Pick any of the 9 themes — it's your choice",
        "Each theme incharge reviews your submission and decides Selected / Not Selected",
    ],
    "gallery": [
        {"src": "/media/img1.jpeg", "alt": "INFRASURE event image 1"},
        {"src": "/media/img2.jpeg", "alt": "INFRASURE event image 2"},
        {"src": "/media/img3.jpeg", "alt": "INFRASURE event image 3"},
        {"src": "/media/img4.jpeg", "alt": "INFRASURE event image 4"},
        {"src": "/media/img5.jpeg", "alt": "INFRASURE event image 5"},
    ],
    "address": "Department of Civil Engineering, IIT Kharagpur, Kharagpur — 721302, West Bengal, India",
}

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
