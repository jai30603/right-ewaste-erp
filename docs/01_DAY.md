📘 DAY 01 — Building the Foundation of Right Ewaste ERP
1. Project Vision

Before writing a single line of code, we decided what we are building.

This is important because many beginners immediately start coding without understanding the problem.

Our goal is not to build a generic ERP.

Our goal is to build an ERP specifically for:

Right Ewaste Recycle Pvt. Ltd.

The ERP will be used only by your father's company.

That decision affected many technical choices.

Because only one company will use it:

No multi-company support
No company switching
Simpler database
Simpler authentication
Faster development

This is our first software engineering lesson.

Understand the business before writing code.

2. Choosing the Technology Stack

We discussed different options.

Android App

Desktop App

Web App

Finally we chose

Web Application

Why?

Because

Runs on every computer
No installation required
Easy to update
Easy to host later
Your father can simply open Chrome

Then we selected the technologies.

Frontend

HTML

Bootstrap

Backend

Python

Flask

Database

SQLite

Version Control

Git

Hosting

Later

Render / Railway / VPS

This combination is simple and perfect for a beginner.

3. Project Architecture

We discussed that professional projects are divided into layers.

Instead of writing everything inside one file,

we divided responsibilities.

Browser

↓

Flask

↓

Routes

↓

Services

↓

Repositories

↓

SQLite

Each layer has one responsibility.

Browser

The user interacts here.

Example

Add Party

Save

Generate Invoice
Flask

Receives requests.

Example

User clicked Save

Flask decides what to do next.

Routes

Example

/party

/material

/sales

Each route opens a page.

Service Layer

Contains business logic.

Example

Calculate GST

Generate Invoice Number

Calculate Grand Total

Business rules belong here.

Repository Layer

Responsible only for database operations.

Example

SELECT

INSERT

UPDATE

DELETE

No calculations.

No GST logic.

Only database.

SQLite

Stores the data permanently.

This architecture is used in real software companies.

4. Database Design

We then designed the database.

Instead of immediately writing Python,

we designed the data first.

Because

Software is built around data.

We created

Company

Stores

Company Name
GST
PAN
Address
Phone

Then

Party

Stores

Customers

Suppliers

Both

Then

Material

Stores

Items that are bought and sold.

Example

Laptop Scrap

PCB Scrap

Plastic

Water Filter Scrap

Then

Sales Invoice

Stores

Invoice Header

Example

Invoice Number

Customer

Date

GST

Grand Total

Then

Sales Invoice Item

Stores

Every row inside an invoice.

Example

Invoice

Laptop Scrap

100 KG

Second Row

PCB Scrap

25 KG

Instead of storing everything inside one table,

we separated Header and Items.

This is how ERP systems are designed.

5. Why Multiple Tables?

Suppose one invoice has

5 materials.

If we stored everything in one table,

the invoice information would repeat 5 times.

Instead

Invoice

↓

Invoice Items

This avoids duplication.

This concept is called

Normalization
6. Learning SQLite

You installed

SQLite

DB Browser

Created

erp.db

Created SQL files

001_company.sql

002_party.sql

003_material.sql

...

Instead of creating tables manually,

we stored SQL inside files.

Professional developers do this because

Easy to edit
Easy to version control
Easy to recreate database
7. Inserting Sample Data

We inserted

Company

Party

Materials

using SQL.

Then verified

SELECT *

This helped understand

INSERT

SELECT

properly.

8. Connecting Python to SQLite

Then we moved to Python.

Created

database.py

Purpose

Create one function

get_connection()

Instead of

sqlite3.connect(...)

everywhere,

we use

get_connection()

One function.

Reusable.

Then

main.py

Connected

Python

↓

SQLite

↓

Read Company

↓

Printed Result

This proved

Python can communicate with the database.

9. Repository Pattern

Instead of SQL inside

main.py

we created

repositories/

Example

party_repository.py

Functions

get_all_parties()

add_party()

update_party()

delete_party()

search_party()

Notice

No Flask.

No HTML.

Only SQL.

This keeps code organized.

10. Service Layer

Then

services/

We started

invoice_service.py

Purpose

Business Logic.

Example

Generate Invoice Number

Calculate GST

Calculate Totals

Create Invoice

Important Lesson

Business Logic

≠

Database Logic

11. GST Logic

Initially

We made

CGST

SGST

always.

Then you asked

Every invoice won't always have CGST and SGST.

Excellent observation.

We corrected the design.

Now

If

Company State

=

Customer State

↓

CGST + SGST

Else

↓

IGST

This is real business logic.

12. Flask

Backend was ready.

Then

Instead of testing

inside

main.py

we decided

Let's create a website.

Installed

Flask

Created

app.py

Started

localhost:5000

Congratulations.

This was your first Flask application.

13. Templates

Created

templates/

Added

dashboard.html

Instead of returning

<h1>Hello</h1>

Flask now returns HTML.

14. Bootstrap

Instead of designing from scratch,

we imported

Bootstrap 5.

Reason

Professional UI

Responsive

Less CSS

Faster Development

15. Party Module

Created

party.html

Displayed

Party List

from SQLite.

This was the first page that

Database

↓

Python

↓

Flask

↓

HTML

↓

Browser

worked together.

16. Add Party Page

Created

add_party.html

Added

Form

↓

User fills details

↓

Clicks Save

↓

POST Request

↓

Repository

↓

SQLite

↓

Redirect

↓

Party List

This was your first complete CRUD workflow.

17. State Dropdown

Instead of typing

Maharashtra

27

every time,

we created

states.py

Python sends

State List

↓

HTML Dropdown

↓

JavaScript

↓

Auto State Code

Cleaner.

Less mistakes.

18. Blueprints

Initially

Everything was inside

app.py

We reorganized.

Created

routes/

Each module now has its own file.

Example

party.py

material.py

sales.py

Benefits

Smaller files

Easy maintenance

Professional architecture

19. Git

Finally

We initialized Git.

Created

.gitignore

README.md

Committed

Initial ERP project setup

Then pushed the project to GitHub.

Now your project has version history and a remote backup.

🎯 What You Learned on Day 1

You didn't just learn Flask or SQLite.

You learned the complete foundation of how a business application is structured:

Analyze the business before coding.
Design the database first.
Separate responsibilities (Routes, Services, Repositories).
Build reusable code.
Use version control from the beginning.
Build features in small, testable steps.
📅 Day 2 Preview

Tomorrow we'll stop doing setup and start building business functionality:

Complete the Party Module (Edit, Delete, Search, Validation).
Build the Material Module.
Start the Sales Invoice Module, where you'll create invoices through the browser with automatic GST calculation and database storage.

From Day 2 onward, every session will add visible functionality to the ERP, bringing it closer to being used in your father's company.