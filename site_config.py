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
    "venue": "IIT Kharagpur Research Park, Kolkata",
    "organizer": "Department of Civil Engineering",
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
        "Student and early-career researcher forums",
        "Industry and technology showcase",
    ],
    "participantspublications": [
        "Researchers and academicians in water and environmental disciplines",
        "Policymakers and government officials",
        "Industry professionals and technology providers",
        "Non-governmental organizations and development agencies",
        "Research scholars, undergraduate & postgraduate students",
        "Conference proceedings with ISBN and Springer book series",
        "Special issues in indexed national or international journals",
    ],

    "submit_rules": [
        "Submit Round 1 with a title and abstract only",
        "Up to 2 submissions per student — any combination of PPT and Poster",
        "Pick any of the 9 themes — it's your choice",
        "Each submission is judged Round 1 (Selected for Round 2 / Not Selected), then you choose PPT or Poster",
        "Round 2: Poster teams submit a revised title and abstract; PPT teams upload a PDF of their work",
        "A final decision — Selected or Not Selected — ends the review process for that submission",
    ],
    "max_pdf_mb": 25,
    "registration_fees": {
        "note": "Early bird registration closes 30 Dec 2026. Spot registration thereafter.",
        "categories": [
            {"label": "Student", "early": "₹2,000", "spot": "₹3,000"},
            {"label": "Faculty / Academic", "early": "₹2,000", "spot": "₹3,000"},
            {"label": "Delegate", "early": "₹6,000", "spot": "₹8,000"},
            {"label": "Foreign Delegate", "early": "$150", "spot": "$200"},
            {"label": "Accompanying Person", "early": "₹2,000", "spot": "₹2,000"},
        ],
    },
    "cfp_timeline": [
        {"label": "Abstract submission open", "date": "10 Sep 2026"},
        {"label": "Abstract submission closes", "date": "15 Oct 2026"},
        {"label": "Acceptance of abstract", "date": "30 Oct 2026"},
        {"label": "Full paper submission", "date": "30 Nov 2026"},
        {"label": "Paper review outcomes", "date": "10 Dec 2026"},
        {"label": "Final paper submission", "date": "20 Dec 2026"},
        {"label": "Early bird registration", "date": "30 Dec 2026"},
    ],
    "gallery": [
        {"src": "/media/img1.jpeg", "alt": "INFRASURE event image 1"},
        {"src": "/media/img2.jpeg", "alt": "INFRASURE event image 2"},
        {"src": "/media/img3.jpeg", "alt": "INFRASURE event image 3"},
        {"src": "/media/img4.jpeg", "alt": "INFRASURE event image 4"},
        {"src": "/media/img5.jpeg", "alt": "INFRASURE event image 5"},
        {"src": "/media/img6.jpeg", "alt": "INFRASURE event image 6"},
        {"src": "/media/img7.jpeg", "alt": "INFRASURE event image 7"},
        {"src": "/media/img8.jpeg", "alt": "INFRASURE event image 8"},
        {"src": "/media/img9.jpeg", "alt": "INFRASURE event image 9"},
    ],
    "address": "Department of Civil Engineering, IIT Kharagpur, Kharagpur — 721302, West Bengal, India",
    "organizing_committee": [
        {
            "group": "Patron",
            "members": [
                {
                    "name": "Prof. Suman Chakraborty",
                    "initials": "SC",
                    "role": "Patron",
                    "affiliation": "Director, IIT Kharagpur",
                    "photo": "/media/peoples/Sumanchakarborty.jpeg",
                },
            ],
        },
        {
            "group": "Chairperson",
            "members": [
                {
                    "name": "Prof. Damodar Maity",
                    "initials": "DM",
                    "role": "Chairperson",
                    "affiliation": "IIT Kharagpur",
                    "photo": "/media/peoples/ProfDamodarMaity.jpeg",
                },
            ],
        },
        {
            "group": "Co-Chairpersons",
            "members": [
                {
                    "name": "Prof. A. K. Gupta",
                    "initials": "AKG",
                    "role": "Co-Chairperson",
                    "affiliation": "IIT Kharagpur",
                    "photo": "/media/peoples/ProfAKGupta.jpeg",
                },
                {
                    "name": "Prof. Amit Shaw",
                    "initials": "AS",
                    "role": "Co-Chairperson",
                    "affiliation": "IIT Kharagpur",
                    "photo": "/media/peoples/ProfAmitShaw.jpeg",
                },
                {
                    "name": "Prof. Anirban Dhar",
                    "initials": "AD",
                    "role": "Co-Chairperson",
                    "affiliation": "IIT Kharagpur",
                    "photo": "/media/peoples/ProfAnirbanDhar.jpeg",
                },
                {
                    "name": "Prof. M. A. Reddy",
                    "initials": "MR",
                    "role": "Co-Chairperson",
                    "affiliation": "IIT Kharagpur",
                    "photo": "/media/peoples/ProfMAReddy.jpeg",
                },
            ],
        },
        {
            "group": "Convener & Co-Convener",
            "members": [
                {
                    "name": "Dr. Manish Pandey",
                    "initials": "MP",
                    "role": "Convener",
                    "affiliation": "IIT Kharagpur",
                    "photo": "/media/peoples/DrManishPandey.jpeg",
                },
                {
                    "name": "Dr. Troyee Tanu Dutta",
                    "initials": "TD",
                    "role": "Co-Convener",
                    "affiliation": "IIT Kharagpur",
                    "photo": "/media/peoples/DrTroyeeTanuDutta.jpeg",
                },
            ],
        },
        {
            "group": "Organizing Secretaries",
            "members": [
                {
                    "name": "Dr. Abhishek Ghosh Dastider",
                    "initials": "AG",
                    "role": "Organizing Secretary",
                    "affiliation": "IIT Kharagpur",
                    "photo": "/media/peoples/DrAbhishekGhoshDastider.jpeg",
                },
                {
                    "name": "Dr. Amit Passi",
                    "initials": "AP",
                    "role": "Organizing Secretary",
                    "affiliation": "IIT Kharagpur",
                    "photo": "/media/peoples/DrAmitPassi.jpeg",
                },
                {
                    "name": "Dr. Gaurav Misuriya",
                    "initials": "GM",
                    "role": "Organizing Secretary",
                    "affiliation": "IIT Kharagpur",
                    "photo": "/media/peoples/DrGauravMisuriya.png",
                },
                {
                    "name": "Dr. Nandan Maiti",
                    "initials": "NM",
                    "role": "Organizing Secretary",
                    "affiliation": "IIT Kharagpur",
                    "photo": "/media/peoples/DrNAndanMaiti.jpeg",
                },
                {
                    "name": "Dr. Pratyush Kumar",
                    "initials": "PK",
                    "role": "Organizing Secretary",
                    "affiliation": "IIT Kharagpur",
                    "photo": "/media/peoples/Photo_pratyush_V1.png",
                },
                {
                    "name": "Dr. Reshma Mohan",
                    "initials": "RM",
                    "role": "Organizing Secretary",
                    "affiliation": "IIT Kharagpur",
                    "photo": 'media/peoples/ReshmaMohan.jpeg',
                },
            ],
        },
        {
            "group": "Treasurer",
            "members": [
                {
                    "name": "Prof. Kousik Deb",
                    "initials": "KD",
                    "role": "Treasurer",
                    "affiliation": "IIT Kharagpur",
                    "photo": 'media/peoples/image.png',
                },
            ],
        },
    ],
    "sponsorship_benefits": {
        "eyebrow": "Partner with us",
        "title": "Sponsorship Benefits",
        "subtitle": "Partner with INFRASURE 2027 and showcase your brand to researchers, industry leaders, and policymakers in sustainable infrastructure.",
        "note": "For custom packages, exhibition details, and invoicing, write to us and we will get back to you as soon as possible.",
        "contact_email": "infrasure2027@civil.iitkgp.ac.in",
        "columns": [
            "Sponsor Category",
            "Sponsorship Amount",
            "Logo on conference banner",
            "Logo displayed at the start of each session",
            "Company logo on conference homepage with hyperlink",
            "Industry Talk (Min)",
            "Complimentary delegate registrations",
            "Invitation to conference dinner for registered delegates",
            "Exhibition space for products / technologies",
        ],
        "tiers": [
            {
                "name": "PLATINUM",
                "amount": "₹8 Lakh",
                "benefits": [True, True, True, "15", "6 Regs", True, True],
            },
            {
                "name": "DIAMOND",
                "amount": "₹6 Lakh",
                "benefits": [False, True, True, "10", "4 Regs", True, True],
            },
            {
                "name": "GOLD",
                "amount": "₹4 Lakh",
                "benefits": [False, False, True, "7", "3 Regs", True, True],
            },
            {
                "name": "SILVER",
                "amount": "₹2 Lakh",
                "benefits": [False, False, True, False, "2 Regs", True, True],
            },
            {
                "name": "BRONZE",
                "amount": "₹1 Lakh",
                "benefits": [False, False, False, False, "1 Reg", False, True],
            },
        ],
    },
        "advisory_committee": {
        "International": [
            "Prof. Ajit Ahlawat, Netherlands",
            "Prof. Anand Puppala, USA",
            "Prof. Ashish Bhaskar, Australia",
            "Prof. Auroop R. Ganguly, USA",
            "Prof. Domenico Santoro, Canada",
            "Prof. Hazi Azamathulla, Trinidad",
            "Dr. Hrishikesh Chandra Gautam, USA",
            "Prof. J. N. Reddy, USA",
            "Prof. Jaan H. Pu, UK",
            "Prof. Juliana B. Jalaludin, Malaysia",
            "Prof. K. V. Krishna Rao, IITB",
            "Prof. Lakshminarayana Rao, IISc",
            "Prof. Lekshmi Mohan V, NITT",
            "Prof. Lelitha Devi Vanajakshi, IITM",
            "Prof. Ludovic Leclercq, France",
            "Prof. M. Parida, IITR",
            "Prof. Manik Barman, Dulith",
            "Prof. Manish Goyal, IITI",
            "Prof. Manousos Valyrakis, Greece",
            "Prof. Md. Rafein Bin Zakaria, Malaysia",
            "Prof. N V Umamahesh, NITW",
            "Prof. Narendra N. Das, USA",
            "Prof. Narasamma Nippatlapalli, IITT",
            "Prof. P. Diplas, USA",
            "Prof. P. K. Sharma, IITR",
            "Prof. P. L. Patel, VNIT",
            "Dr. Pankaj K Gupta, Jal Shakti",
            "Prof. Pradeep K. Ramancharla, CBRI",
            "Prof. Praveen Kumar, IITR",
            "Prof. Rajib K. Bhattacharjya, IITG",
            "Prof. Ramakar Jha, NIT Patna",
            "Prof. S. Dey, IITGn",
            "Prof. S. K. Bhattacharyya, Shiv Nadar",
            "Prof. S. M. Yadav, SVNIT Surat",
            "Prof. Satish Nagarajaiah, USA",
            "Prof. Vivek Tandon, USA",
        ],

        "National": [
            "Prof. A. K. Nema, IITD",
            "Prof. Ananth Ramaswamy, IISc",
            "Prof. Anil Kumar Gupta, IITR",
            "Prof. Animesh Das, IITK",
            "Prof. Arindam Dey, IITG",
            "Prof. B. R. Chahar, IITD",
            "Prof. Basudev Biswal, IITB",
            "Mr. Bhavay Sharma, WRI",
            "Prof. Bimlesh Kumar, IITG",
            "Dr. C. Ravi Shekhar, CRRI",
            "Prof. C. S. P. Ojha, IITR",
            "Prof. D. Nagesh Kumar, IISc",
            "Prof. Deepankar Choudhury, IITB",
            "Prof. G. V. Ramana, IITD",
            "Prof. H. L. Tiwari, NIT Bhopal",
            "Prof. K. N. Satyanarayana, IITT",
            "Prof. K. V. Jayakumar, IIT Dharwad",
            "Prof. S. N. Kuiry, IITM",
            "Prof. Sarat Kumar Das, IIT (ISM)",
            "Prof. Seetha N, IITH",
            "Prof. Shiva Nagendra SM, IITM",
            "Prof. Shriniwas Arkatkar, SVNIT",
            "Prof. Sireesh S, IITH",
            "Prof. Subashisa Dutta, IITG",
            "Prof. Subhadeep Banerjee, IITM",
            "Prof. Sudipta Sarkar, IITR",
            "Prof. T. I. Eldho, IITB",
            "Prof. V. Jothiprakash, IITB",
            "Prof. V. R. Desai, IIT Dharwad",
            "Prof. V. Sundar, IITM",
            "Prof. V. V. Srinivas, IISc",
            "Prof. Vasant Matsagar, IITD",
            "Prof. Venu Chandra, IITM",
            "Prof. Vimal Mishra, IITGn",
            "Prof. Z. Ahmad, IITR",
        ],
    },
}

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
