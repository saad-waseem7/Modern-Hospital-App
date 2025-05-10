-- Hospital Management System Schema
USE master;
GO
CREATE DATABASE modHospital;
GO
USE modHospital

-- Drop existing tables if they exist
IF OBJECT_ID('RoomAssignments', 'U') IS NOT NULL DROP TABLE RoomAssignments;
IF OBJECT_ID('InsuranceClaims', 'U') IS NOT NULL DROP TABLE InsuranceClaims;
IF OBJECT_ID('Feedback', 'U') IS NOT NULL DROP TABLE Feedback;
IF OBJECT_ID('EmergencyCases', 'U') IS NOT NULL DROP TABLE EmergencyCases;
IF OBJECT_ID('LabReports', 'U') IS NOT NULL DROP TABLE LabReports;
IF OBJECT_ID('Prescriptions', 'U') IS NOT NULL DROP TABLE Prescriptions;
IF OBJECT_ID('Appointments', 'U') IS NOT NULL DROP TABLE Appointments;
IF OBJECT_ID('Bills', 'U') IS NOT NULL DROP TABLE Bills;
IF OBJECT_ID('Patients', 'U') IS NOT NULL DROP TABLE Patients;
IF OBJECT_ID('Doctors', 'U') IS NOT NULL DROP TABLE Doctors;
IF OBJECT_ID('PharmacyInventory', 'U') IS NOT NULL DROP TABLE PharmacyInventory;
IF OBJECT_ID('Staff', 'U') IS NOT NULL DROP TABLE Staff;
IF OBJECT_ID('Rooms', 'U') IS NOT NULL DROP TABLE Rooms;
IF OBJECT_ID('Users', 'U') IS NOT NULL DROP TABLE Users;
IF OBJECT_ID('Roles', 'U') IS NOT NULL DROP TABLE Roles;

-- Create Roles table first since it's referenced by Users
CREATE TABLE Roles (
    RoleID INT PRIMARY KEY IDENTITY,
    RoleName NVARCHAR(50) UNIQUE NOT NULL
);

-- Create Users table
CREATE TABLE Users (
    UserID INT PRIMARY KEY IDENTITY,
    Username NVARCHAR(50) UNIQUE NOT NULL,
    Password NVARCHAR(255) NOT NULL,
    RoleID INT NOT NULL FOREIGN KEY REFERENCES Roles(RoleID),
    CreatedAt DATETIME DEFAULT GETDATE(),
    LastLogin DATETIME NULL
);

-- Create Patients table with UserID reference
CREATE TABLE Patients (
    PatientID INT PRIMARY KEY IDENTITY,
    Name NVARCHAR(100) NOT NULL,
    DOB DATE NOT NULL,
    Gender NVARCHAR(10) NOT NULL,
    Contact NVARCHAR(50) NOT NULL,
    Address NVARCHAR(255) NOT NULL,
    MedicalHistory TEXT NULL,
    UserID INT NULL UNIQUE FOREIGN KEY REFERENCES Users(UserID)
    -- UNIQUE ensures that a user can only be associated with one patient record
);

-- Create Doctors table with UserID reference
CREATE TABLE Doctors (
    DoctorID INT PRIMARY KEY IDENTITY,
    Name NVARCHAR(100) NOT NULL,
    Specialty NVARCHAR(100) NOT NULL,
    Availability NVARCHAR(100) NOT NULL,
    UserID INT NULL UNIQUE FOREIGN KEY REFERENCES Users(UserID)
    -- UNIQUE ensures that a user can only be associated with one doctor record
);

-- Create Appointments table
CREATE TABLE Appointments (
    AppointmentID INT PRIMARY KEY IDENTITY,
    PatientID INT NOT NULL FOREIGN KEY REFERENCES Patients(PatientID),
    DoctorID INT NOT NULL FOREIGN KEY REFERENCES Doctors(DoctorID),
    DateTime DATETIME NOT NULL,
    Status NVARCHAR(50) NOT NULL,
    Notes TEXT NULL,
    CreatedAt DATETIME DEFAULT GETDATE()
);

-- Create Bills table
CREATE TABLE Bills (
    BillID INT PRIMARY KEY IDENTITY,
    PatientID INT NOT NULL FOREIGN KEY REFERENCES Patients(PatientID),
    Amount DECIMAL(10,2) NOT NULL,
    Status NVARCHAR(50) NOT NULL,
    Description TEXT NULL,
    CreatedAt DATETIME DEFAULT GETDATE(),
    UpdatedAt DATETIME NULL
);

-- Create Prescriptions table
CREATE TABLE Prescriptions (
    PrescriptionID INT PRIMARY KEY IDENTITY,
    PatientID INT NOT NULL FOREIGN KEY REFERENCES Patients(PatientID),
    DoctorID INT NOT NULL FOREIGN KEY REFERENCES Doctors(DoctorID),
    Medication TEXT NOT NULL,
    Dosage TEXT NOT NULL,
    DateIssued DATETIME DEFAULT GETDATE(),
    ValidUntil DATETIME NULL
);

-- Create PharmacyInventory table
CREATE TABLE PharmacyInventory (
    ItemID INT PRIMARY KEY IDENTITY,
    Name NVARCHAR(100) NOT NULL,
    Stock INT NOT NULL,
    Threshold INT NOT NULL,
    Price DECIMAL(10,2) NULL,
    LastUpdated DATETIME DEFAULT GETDATE()
);

-- Create LabReports table
CREATE TABLE LabReports (
    ReportID INT PRIMARY KEY IDENTITY,
    PatientID INT NOT NULL FOREIGN KEY REFERENCES Patients(PatientID),
    TestType NVARCHAR(100) NOT NULL,
    Result TEXT NOT NULL,
    DateTaken DATETIME NOT NULL,
    DoctorID INT NULL FOREIGN KEY REFERENCES Doctors(DoctorID)
);

-- Create Staff table
CREATE TABLE Staff (
    StaffID INT PRIMARY KEY IDENTITY,
    Name NVARCHAR(100) NOT NULL,
    Role NVARCHAR(50) NOT NULL,
    Contact NVARCHAR(50) NOT NULL,
    UserID INT NULL UNIQUE FOREIGN KEY REFERENCES Users(UserID)
);

-- Create EmergencyCases table
CREATE TABLE EmergencyCases (
    CaseID INT PRIMARY KEY IDENTITY,
    PatientID INT NOT NULL FOREIGN KEY REFERENCES Patients(PatientID),
    CaseDetails TEXT NOT NULL,
    AmbulanceAssigned BIT NOT NULL,
    CaseDate DATETIME DEFAULT GETDATE(),
    ResolvedDate DATETIME NULL
);

-- Create Rooms table
CREATE TABLE Rooms (
    RoomID INT PRIMARY KEY IDENTITY,
    RoomNumber NVARCHAR(20) NOT NULL,
    Type NVARCHAR(50) NOT NULL,
    Status NVARCHAR(20) NOT NULL,
    PricePerDay DECIMAL(10,2) NULL
);

-- Create RoomAssignments table
CREATE TABLE RoomAssignments (
    AssignmentID INT PRIMARY KEY IDENTITY,
    PatientID INT NOT NULL FOREIGN KEY REFERENCES Patients(PatientID),
    RoomID INT NOT NULL FOREIGN KEY REFERENCES Rooms(RoomID),
    StartDate DATE NOT NULL,
    EndDate DATE NULL,
    AssignedBy INT NULL FOREIGN KEY REFERENCES Staff(StaffID)
);

-- Create InsuranceClaims table
CREATE TABLE InsuranceClaims (
    ClaimID INT PRIMARY KEY IDENTITY,
    PatientID INT NOT NULL FOREIGN KEY REFERENCES Patients(PatientID),
    Insurer NVARCHAR(100) NOT NULL,
    PolicyNumber NVARCHAR(100) NOT NULL,
    ClaimStatus NVARCHAR(50) NOT NULL,
    ClaimDate DATETIME DEFAULT GETDATE(),
    Amount DECIMAL(10,2) NULL
);

-- Create Feedback table
CREATE TABLE Feedback (
    FeedbackID INT PRIMARY KEY IDENTITY,
    PatientID INT NOT NULL FOREIGN KEY REFERENCES Patients(PatientID),
    DoctorID INT NOT NULL FOREIGN KEY REFERENCES Doctors(DoctorID),
    Rating INT NOT NULL,
    Comments TEXT NULL,
    FeedbackDate DATETIME DEFAULT GETDATE()
);

-- Insert roles including Patient role
INSERT INTO Roles (RoleName) VALUES
('Admin'),
('Doctor'),
('Patient'),
('Receptionist'),
('Nurse');

-- Insert hardcoded admin user (USERNAME: admin@hospital, PASSWORD: admin123)
-- IMPORTANT: This is a default admin account - change the password in production!
INSERT INTO Users (Username, Password, RoleID) VALUES
('admin@hospital', 'admin123', (SELECT RoleID FROM Roles WHERE RoleName = 'Admin'));

-- Insert sample admin user
INSERT INTO Users (Username, Password, RoleID) VALUES
('admin', 'admin123', (SELECT RoleID FROM Roles WHERE RoleName = 'Admin'));

-- Sample doctors with users
INSERT INTO Users (Username, Password, RoleID) VALUES
('dr.alice', 'pass123', (SELECT RoleID FROM Roles WHERE RoleName = 'Doctor')),
('dr.bob', 'pass123', (SELECT RoleID FROM Roles WHERE RoleName = 'Doctor'));

INSERT INTO Doctors (Name, Specialty, Availability, UserID) VALUES
('Dr. Alice Brown', 'Cardiology', 'Mon-Fri 9am-5pm', (SELECT UserID FROM Users WHERE Username = 'dr.alice')),
('Dr. Bob White', 'Neurology', 'Tue-Thu 10am-4pm', (SELECT UserID FROM Users WHERE Username = 'dr.bob'));

-- Sample patients with users
INSERT INTO Users (Username, Password, RoleID) VALUES
('john.doe', 'pass123', (SELECT RoleID FROM Roles WHERE RoleName = 'Patient')),
('jane.smith', 'pass123', (SELECT RoleID FROM Roles WHERE RoleName = 'Patient'));

INSERT INTO Patients (Name, DOB, Gender, Contact, Address, MedicalHistory, UserID) VALUES
('John Doe', '1985-06-15', 'Male', '123-456-7890', '123 Elm Street', 'Diabetes', (SELECT UserID FROM Users WHERE Username = 'john.doe')),
('Jane Smith', '1990-02-20', 'Female', '234-567-8901', '456 Oak Avenue', 'None', (SELECT UserID FROM Users WHERE Username = 'jane.smith'));

-- Sample staff
INSERT INTO Users (Username, Password, RoleID) VALUES
('reception1', 'welcome', (SELECT RoleID FROM Roles WHERE RoleName = 'Receptionist'));

INSERT INTO Staff (Name, Role, Contact, UserID) VALUES
('Tom Green', 'Receptionist', '555-1234', (SELECT UserID FROM Users WHERE Username = 'reception1')),
('Sara Blue', 'Nurse', '555-5678', NULL);

-- Sample room data
INSERT INTO Rooms (RoomNumber, Type, Status, PricePerDay) VALUES
('101A', 'ICU', 'Occupied', 500.00),
('102B', 'General', 'Available', 200.00);

-- Sample appointment data
INSERT INTO Appointments (PatientID, DoctorID, DateTime, Status) VALUES
(1, 1, '2025-05-05 10:00:00', 'Scheduled'),
(2, 2, '2025-05-06 11:30:00', 'Completed');

-- Sample prescription data
INSERT INTO Prescriptions (PatientID, DoctorID, Medication, Dosage) VALUES
(1, 1, 'Aspirin', '1 tablet daily'),
(2, 2, 'Ibuprofen', '200mg twice daily');

-- Sample bill data
INSERT INTO Bills (PatientID, Amount, Status, Description) VALUES
(1, 200.50, 'Paid', 'Consultation fee'),
(2, 350.75, 'Unpaid', 'Lab tests');

-- Sample pharmacy data
INSERT INTO PharmacyInventory (Name, Stock, Threshold, Price) VALUES
('Aspirin', 100, 20, 5.99),
('Ibuprofen', 150, 30, 7.99);

-- Sample lab reports
INSERT INTO LabReports (PatientID, TestType, Result, DateTaken, DoctorID) VALUES
(1, 'Blood Test', 'Normal', '2025-05-01', 1),
(2, 'MRI', 'Minor issues', '2025-05-02', 2);

-- Sample emergency cases
INSERT INTO EmergencyCases (PatientID, CaseDetails, AmbulanceAssigned) VALUES
(1, 'Car accident injury', 1),
(2, 'Heart attack', 1);

-- Sample room assignments
INSERT INTO RoomAssignments (PatientID, RoomID, StartDate, EndDate) VALUES
(1, 1, '2025-05-01', NULL),
(2, 2, '2025-05-03', '2025-05-05');

-- Sample insurance claims
INSERT INTO InsuranceClaims (PatientID, Insurer, PolicyNumber, ClaimStatus, Amount) VALUES
(1, 'MediCare', 'MC12345', 'Approved', 500.00),
(2, 'HealthNet', 'HN67890', 'Pending', 750.00);

-- Sample feedback
INSERT INTO Feedback (PatientID, DoctorID, Rating, Comments) VALUES
(1, 1, 5, 'Excellent care'),
(2, 2, 4, 'Good service');