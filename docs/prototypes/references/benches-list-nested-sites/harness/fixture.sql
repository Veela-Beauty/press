DROP DATABASE IF EXISTS qbcheck_rg;
CREATE DATABASE qbcheck_rg;
USE qbcheck_rg;
CREATE TABLE `tabRelease Group` (name VARCHAR(140) PRIMARY KEY, title VARCHAR(140), team VARCHAR(140), enabled INT);
CREATE TABLE `tabRelease Group Server` (name VARCHAR(140) PRIMARY KEY, parent VARCHAR(140), parenttype VARCHAR(140), server VARCHAR(140), idx INT);
CREATE TABLE `tabServer` (name VARCHAR(140) PRIMARY KEY, title VARCHAR(140), provider VARCHAR(140));
CREATE TABLE `tabSite` (name VARCHAR(140) PRIMARY KEY, `group` VARCHAR(140), status VARCHAR(40));
CREATE TABLE `tabBench` (name VARCHAR(140) PRIMARY KEY, `group` VARCHAR(140), status VARCHAR(40));
INSERT INTO `tabRelease Group` VALUES ('rg-two-servers','Accurate System Bench 15','team-1',1), ('rg-no-server','Accurate V16','team-1',1), ('rg-other-team','Foreign','team-2',1), ('rg-disabled','Old','team-1',0);
-- idx 2 inserted first, so a missing ORDER BY idx would pick the wrong server
INSERT INTO `tabRelease Group Server` VALUES ('r2','rg-two-servers','Release Group','u4-default',2), ('r1','rg-two-servers','Release Group','press-f1',1), ('r3','rg-other-team','Release Group','press-f1',1);
INSERT INTO `tabServer` VALUES ('press-f1','press-f1 (Hetzner, Falkenstein)','Hetzner'), ('u4-default','u4','Generic');
INSERT INTO `tabSite` VALUES ('a','rg-two-servers','Active'), ('b','rg-two-servers','Archived'), ('c','rg-two-servers','Active');
INSERT INTO `tabBench` VALUES ('bench-0015','rg-two-servers','Active');
