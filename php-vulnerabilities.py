import sublime
import sublime_plugin

import re

rules = [
	(r'''\b(include|require)(_once){0,1}(\s{1,5}|\s{0,5}\().{0,60}\$(?!.*(this->))\w{1,20}((\[["']|\[)\${0,1}[\w\[\]"']{0,30}){0,1}''', '文件包含函数中存在变量,可能存在文件包含漏洞'),
	(r'''\bpreg_replace\(\s{0,5}.*/[is]{0,2}e[is]{0,2}["']\s{0,5},(.*\$.*,|.*,.*\$)''', 'preg_replace的/e模式，且有可控变量，可能存在代码执行漏洞'),
	(r'''\bphpinfo\s{0,5}\(\s{0,5}\)''', 'phpinfo()函数，可能存在敏感信息泄露漏洞'),
	(r'''\bcall_user_func(_array){0,1}\(\s{0,5}\$\w{1,15}((\[["']|\[)\${0,1}[\w\[\]"']{0,30}){0,1}''', 'call_user_func函数参数包含变量，可能存在代码执行漏洞'),
	(r'''\b(file_get_contents|fopen|readfile|fgets|fread|parse_ini_file|highlight_file|fgetss|show_source)\s{0,5}\(.{0,40}\$\w{1,15}((\[["']|\[)\${0,1}[\w\[\]"']{0,30}){0,1}''', '读取文件函数中存在变量，可能存在任意文件读取漏洞'),
	(r'''\b(system|passthru|pcntl_exec|shell_exec|escapeshellcmd|exec)\s{0,10}\(.{0,40}\$\w{1,20}((\[["']|\[)\${0,1}[\w\[\]"']{0,30}){0,1}''', '命令执行函数中存在变量，可能存在任意命令执行漏洞'),
	(r'''\b(mb_){0,1}parse_str\s{0,10}\(.{0,40}\$\w{1,20}((\[["']|\[)\${0,1}[\w\[\]"']{0,30}){0,1}''', 'parse_str函数中存在变量,可能存在变量覆盖漏洞'),
	(r'''\${{0,1}\$\w{1,20}((\[["']|\[)\${0,1}[\w\[\]"']{0,30}){0,1}\s{0,4}=\s{0,4}.{0,20}\$\w{1,20}((\[["']|\[)\${0,1}[\w\[\]"']{0,30}){0,1}''', '双$$符号可能存在变量覆盖漏洞'),
	(r'''["'](HTTP_CLIENT_IP|HTTP_X_FORWARDED_FOR|HTTP_REFERER)["']''', '获取IP地址方式可伪造，HTTP_REFERER可伪造，常见引发SQL注入等漏洞'),
	(r'''\b(unlink|copy|fwrite|file_put_contents|bzopen)\s{0,10}\(.{0,40}\$\w{1,20}((\[["']|\[)\${0,1}[\w\[\]"']{0,30}){0,1}''', '文件操作函数中存在变量，可能存在任意文件读取/删除/修改/写入等漏洞'),
	(r'''\b(extract)\s{0,5}\(.{0,30}\$\w{1,20}((\[["']|\[)\${0,1}[\w\[\]"']{0,30}){0,1}\s{0,5},{0,1}\s{0,5}(EXTR_OVERWRITE){0,1}\s{0,5}\)''', 'extract函数中存在变量，可能存在变量覆盖漏洞'),
	(r'''\$\w{1,20}((\[["']|\[)\${0,1}[\w\[\]"']{0,30}){0,1}\s{0,5}\(\s{0,5}\$_(POST|GET|REQUEST|SERVER)\[.{1,20}\]''', '可能存在代码执行漏洞,或者此处是后门'),
	(r'''^(?!.*\baddslashes).{0,40}\b((raw){0,1}urldecode|stripslashes)\s{0,5}\(.{0,60}\$\w{1,20}((\[["']|\[)\${0,1}[\w\[\]"']{0,30}){0,1}''', 'urldecode绕过GPC,stripslashes会取消GPC转义字符'),
	(r'''`\$\w{1,20}((\[["']|\[)\${0,1}[\w\[\]"']{0,30}){0,1}`''', '``反引号中包含变量，变量可控会导致命令执行漏洞'),
	(r'''\barray_map\s{0,4}\(\s{0,4}.{0,20}\$\w{1,20}((\[["']|\[)\${0,1}[\w\[\]"']{0,30}){0,1}\s{0,4}.{0,20},''', 'array_map参数包含变量，变量可控可能会导致代码执行漏洞'),
	(r'''select\s{1,4}.{1,60}from.{1,50}\bwhere\s{1,3}.{1,50}=["\s\.]{0,10}\$\w{1,20}((\[["']|\[)\${0,1}[\w\[\]"']{0,30}){0,1}''', 'SQL语句select中条件变量无单引号保护，可能存在SQL注入漏洞'),
	(r'''delete\s{1,4}from.{1,20}\bwhere\s{1,3}.{1,30}=["\s\.]{0,10}\$\w{1,20}((\[["']|\[)\${0,1}[\w\[\]"']{0,30}){0,1}''', 'SQL语句delete中条件变量无单引号保护，可能存在SQL注入漏洞'),
	(r'''insert\s{1,5}into\s{1,5}.{1,60}\$\w{1,20}((\[["']|\[)\${0,1}[\w\[\]"']{0,30}){0,1}''', 'SQL语句insert中插入变量无单引号保护，可能存在SQL注入漏洞'),
	(r'''update\s{1,4}.{1,30}\s{1,3}set\s{1,5}.{1,60}\$\w{1,20}((\[["']|\[)\${0,1}[\w\[\]"']{0,30}){0,1}''', 'SQL语句delete中条件变量无单引号保护，可能存在SQL注入漏洞'),
	(r'''\b(eval|assert)\s{0,10}\(.{0,60}\$\w{1,20}((\[["']|\[)\${0,1}[\w\[\]"']{0,30}){0,1}''', 'eval或者assertc函数中存在变量，可能存在代码执行漏洞'),
	(r'''\b(echo|print|print_r)\s{0,5}\({0,1}.{0,60}\$_(POST|GET|REQUEST|SERVER)''', 'echo等输出中存在可控变量，可能存在XSS漏洞'),
	(r'''(\bheader\s{0,5}\(.{0,30}|window.location.href\s{0,5}=\s{0,5})\$_(POST|GET|REQUEST|SERVER)''', 'header函数或者js location有可控参数，存在任意跳转或http头污染漏洞'),
	(r'''\bmove_uploaded_file\s{0,5}\(''', '存在文件上传，注意上传类型是否可控'),
]

class VulnerabilitiesofphpCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		filename = self.view.file_name()
		suffixes = [
			"php",
			"php3",
			"php4",
			"php5",
			"php7",
			"phps",
			"pht",
			"phtm",
			"phtml",
		]
		file_extension = filename.split(".")[-1]
		if file_extension in suffixes:
			lines = self.view.substr(sublime.Region(0, self.view.size())).split("\n")
			position = 0
			vulnerabilities = []
			line_number = 0
			for line in lines:
				line_number += 1
				for rule in rules:
					result = re.search(rule[0], line)
					if result != None:
						data = {
							"filename":filename,
							"line":line_number,
							"hint":rule[1],
						}
						hint = "\n// Vulnerability: %s\n" % rule[1]
						self.view.insert(edit, position, hint)
						position += len(hint)
						vulnerabilities.append(data)
				position += len(line) + len("\n")
			print(vulnerabilities)
		else:
			print("File extension (%s) not supported!" % (file_extension))
