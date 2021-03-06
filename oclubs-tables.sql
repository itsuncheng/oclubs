CREATE DATABASE oclubs CHARACTER SET utf8;

USE oclubs;

CREATE TABLE user (
	user_id int unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT,
	user_login_name varchar(255) NOT NULL, # username used to login, currently gnumberid
	user_gnumber_id varchar(255), # student ID starting with G
	user_short_id varchar(255), # 5-digit student ID
	user_nick_name varchar(255) NOT NULL,
	user_passport_name varchar(255) NOT NULL,
	user_password tinyblob,
	user_initalized boolean NOT NULL DEFAULT false,
	user_picture int NOT NULL, # Foreign key to upload.upload_id
	user_email tinytext NOT NULL,
	user_phone bigint,
	user_type tinyint NOT NULL, # Enum UserType
	user_grade tinyint, # NULL for teachers
	user_class tinyint # NULL for teachers
);

CREATE UNIQUE INDEX user_login_name ON user (user_login_name);
CREATE INDEX user_passport_name ON user (user_passport_name);

CREATE TABLE club (
	club_id int unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT,
	club_name varchar(255) NOT NULL,
	club_teacher int NOT NULL, # Foreign key to user.user_id
	club_leader int NOT NULL, # Foreign key to user.user_id
	club_intro tinytext NOT NULL,
	club_picture int NOT NULL, # Foreign key to upload.upload_id
	club_desc int NOT NULL, # Foreign key to text.text_id
	club_location varchar(255) NOT NULL,
	club_inactive boolean NOT NULL,
	club_type tinyint NOT NULL, # 1 = academics, 2 = sports, 3 = arts, 4 = services, 5 = entertainment, 6 = others, 7 = school teams
	club_joinmode tinyint NOT NULL, # 1 = free join, 2 = by invitation,
	club_reactivate boolean NOT NULL,
	club_reservation_allowed boolean NOT NULL DEFAULT true, # true = allowed, false = not allowed
	club_smartboard_allowed boolean NOT NULL DEFAULT true, # true = allowed, false = not allowed
	club_smartboard_teacherapp_bypass boolean NOT NULL DEFAULT false, # true = bypass, false = no bypass
	club_smartboard_directorapp_bypass boolean NOT NULL DEFAULT false # true = bypass, false = no bypass
);

CREATE INDEX club_name ON club (club_name);
CREATE INDEX club_teacher ON club (club_teacher);
CREATE INDEX club_leader ON club (club_leader);


CREATE TABLE club_member (
	cm_club int NOT NULL, # Foreign key to club.club_id
	cm_user int NOT NULL, # Foreign key to user.user_id
	PRIMARY KEY (cm_club, cm_user)
);

#CREATE UNIQUE INDEX cm_club_user ON club_member (cm_club,cm_user);
CREATE INDEX cm_club ON club_member (cm_club);
CREATE INDEX cm_user ON club_member (cm_user);


CREATE TABLE activity (
	act_id int unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT,
	act_name varchar(255) NOT NULL,
	act_club int NOT NULL, # Foreign key to club.club_id
	act_desc int NOT NULL, # Foreign key to text.text_id
	act_date int unsigned NOT NULL,
	act_time tinyint NOT NULL, # 0 = unknown, 1 = noon, 2 = afterschool, 3 = hongmei, 4 = others
	act_location varchar(255) NOT NULL,
	act_cas int NOT NULL, # CAS hours
	act_post int NOT NULL, # Foreign key to text.text_id
	act_selections varchar(255) NOT NULL, # stores object in JSON
	act_reservation int, # Foreign key to reservation.reservations_id
);

CREATE INDEX act_club ON activity (act_club);
CREATE INDEX act_post ON activity (act_post);
CREATE INDEX act_date ON activity (act_date);
CREATE INDEX act_time ON activity (act_time);
CREATE INDEX act_reservation ON activity (act_reservation);


CREATE TABLE act_pic (
	actpic_act int NOT NULL, # Foreign key to activity.act_id
	actpic_upload int NOT NULL, # Foreign key to upload.upload_id
	PRIMARY KEY (actpic_act, actpic_upload)
);

#CREATE UNIQUE INDEX actpic_act_upload ON act_pic (actpic_act, actpic_upload);
CREATE INDEX actpic_act ON act_pic (actpic_act);
CREATE INDEX actpic_upload ON act_pic (actpic_upload);


CREATE TABLE attendance (
	att_act int NOT NULL, # Foreign key to activity.activity_id
	att_user int NOT NULL, # Foreign key to user.user_id
	PRIMARY KEY (att_act, att_user)
);

#CREATE UNIQUE INDEX att_act_user ON attendance (att_act, att_user);
CREATE INDEX att_act ON attendance (att_act);
CREATE INDEX att_user ON attendance (att_user);


CREATE TABLE text (
	text_id int unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT,
	text_club int NOT NULL, # Foreign key to club.club_id
	text_user int NOT NULL, # Foreign key to user.user_id
	text_data mediumblob NOT NULL, # data depends on flags
	text_flags tinyblob NOT NULL # comma-separated list of gzip,external
);

CREATE INDEX text_club ON text (text_club);
CREATE INDEX text_user ON text (text_user);


CREATE TABLE upload (
	upload_id int unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT,
	upload_club int NOT NULL, # Foreign key to club.club_id
	upload_user int NOT NULL, # Foreign key to user.user_id
	upload_loc varchar(255) NOT NULL,
	upload_mime varchar(255) NOT NULL # MIME type
);

CREATE INDEX upload_club ON upload (upload_club);
CREATE INDEX upload_user ON upload (upload_user);


CREATE TABLE notification (
	notification_id int unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT,
	notification_user int NOT NULL, # Foreign key to user.user_id
	notification_text varchar(255) NOT NULL,
	notification_isread boolean NOT NULL,
	notification_date int NOT NULL
);

CREATE INDEX notification_user ON notification (notification_user);


CREATE TABLE signup (
	signup_act int NOT NULL, # Foreign key to act.act_id
	signup_user int NOT NULL, # Foreign key to user.user_id
	signup_consentform boolean NOT NULL,
	signup_selection varchar(255) NOT NULL,
	PRIMARY KEY (signup_act, signup_user)
);

CREATE INDEX signup_act ON signup (signup_act);
CREATE INDEX signup_user ON signup (signup_user);


CREATE TABLE invitation (
	invitation_club int NOT NULL, # Foreign key to club.club_id
	invitation_user int NOT NULL, # Foreign key to user.user_id
	invitation_date int NOT NULL,
	PRIMARY KEY (invitation_club, invitation_user)
);

CREATE INDEX invitation_user ON invitation (invitation_user);


CREATE TABLE preferences (
	pref_user int NOT NULL, # Foreign key to user.user_id
	pref_type varchar(255) NOT NULL,
	pref_value varchar(255) NOT NULL,
	PRIMARY KEY (pref_user, pref_type)
);

CREATE INDEX pref_user ON preferences (pref_user);

CREATE TABLE classroom (
	room_id int unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT,
	room_number varchar(16) NOT NULL,
	room_studentsToUseLunch boolean NOT NULL, # true = available to students, false = not available to students
	room_studentsToUseAfternoon boolean NOT NULL, # true = available to students, false = not available to students
	room_building tinyint NOT NULL, # Enum Building
	room_desc varchar(255) # optional descriptors (eg ASB only)
);

CREATE INDEX room_number ON classroom (room_number);

CREATE TABLE reservation (
	res_id int unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT,
	res_activity int, # Foreign key to act.act_id
	res_date int unsigned NOT NULL, # The date when the reservation is effective
	res_date_of_res int unsigned NOT NULL, # The date when the reservation was created
	res_timeslot tinyint NOT NULL, # based on ActivityTime enum
	res_status tinyint NOT NULL, # 1 = club not yet paired with activity, # 2 = club paired with activity,  # 3 = non-club
	res_activity_name varchar(255),
	res_reserver_name varchar(255),
	res_reserver_club int, # Foreign key to club.club_id
	res_owner int NOT NULL, # Foreign key to user.user_id
	res_classroom int NOT NULL, # Foreign key to classroom.room_id
	res_SBNeeded boolean NOT NULL DEFAULT false, # true = need smartboard, false = no need smartboard
	res_SBAppDesc varchar(512),
	res_instructors_approval boolean NOT NULL DEFAULT false,
	res_directors_approval boolean NOT NULL DEFAULT false,
	res_SBApp_status tinyint NOT NULL DEFAULT 0 # based on SBAppStatus enum
);

CREATE INDEX res_activity ON reservation (res_activity);
CREATE INDEX res_status ON reservation (res_status);
CREATE INDEX res_SBNeeded ON reservation (res_SBNeeded);
CREATE INDEX res_SBApp_status ON reservation (res_SBApp_status);
