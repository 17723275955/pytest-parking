#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time   : 2022/3/28 12:52
# @Author : 余少琪
import os
import random
import urllib

import requests
from typing import Any
from utils.otherUtils.get_conf_data import sql_switch
from requests_toolbelt import MultipartEncoder
from utils.logUtils.logDecoratorl import log_decorator
from utils.mysqlUtils.mysqlControl import MysqlDB
from Enums.requestType_enum import RequestType
from Enums.yamlData_enum import YAMLDate
from common.setting import ConfigHandler
from utils.logUtils.runTimeDecoratorl import execution_duration
from utils.otherUtils.allureDate.allure_tools import allure_step, allure_step_no, allure_attach
from utils.readFilesUtils.regularControl import cache_regular
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class RequestControl:
    """ 封装请求 """

    @classmethod
    def _check_params(cls, response, yaml_data, headers, cookie, res_time, status_code) -> Any:
        """ 抽离出通用模块，判断 http_request 方法中的一些数据校验 """
        # 判断数据库开关，开启状态，则返回对应的数据
        if sql_switch() and yaml_data['sql'] is not None:
            sql_data = MysqlDB().assert_execution(sql=yaml_data['sql'], resp=response)
            return {"response_data": response, "sql_data": sql_data, "yaml_data": yaml_data,
                    "headers": headers, "cookie": cookie, "res_time": res_time, "status_code": status_code}
        else:
            # 数据库关闭走的逻辑
            res = response
            return {"response_data": res, "sql_data": {"sql": None}, "yaml_data": yaml_data,
                    "headers": headers, "cookie": cookie, "res_time": res_time, "status_code": status_code}

    @classmethod
    def file_data_exit(cls, yaml_data, file_data):
        """判断上传文件时，data参数是否存在"""
        # 兼容又要上传文件，又要上传其他类型参数
        try:
            for key, value in yaml_data[YAMLDate.DATA.value]['data'].items():
                file_data[key] = value
        except KeyError:
            pass

    @classmethod
    def multipart_data(cls, file_data):
        multipart = MultipartEncoder(
            fields=file_data,  # 字典格式
            boundary='-----------------------------' + str(random.randint(int(1e28), int(1e29 - 1)))
        )
        return multipart

    @classmethod
    def check_headers_str_null(cls, headers):
        """
        兼容用户未填写headers或者header值为int
        @return:
        """
        if headers is None:
            return {"headers": None}
        else:
            for k, v in headers.items():
                if not isinstance(v, str):
                    headers[k] = str(v)
            return headers

    @classmethod
    def multipart_in_headers(cls, request_data, header):

        """ 判断处理header为 Content-Type: multipart/form-data"""
        if header is None:
            return request_data, {"headers": None}
        else:
            # 将header中的int转换成str
            for k, v in header.items():
                if not isinstance(v, str):
                    header[k] = str(v)
            if "multipart/form-data" in str(header.values()):
                # 判断请求参数不为空, 并且参数是字典类型
                if request_data and isinstance(request_data, dict):
                    # 当 Content-Type 为 "multipart/form-data"时，需要将数据类型转换成 str
                    for k, v in request_data.items():
                        if not isinstance(v, str):
                            request_data[k] = str(v)

                    request_data = MultipartEncoder(request_data)
                    header['Content-Type'] = request_data.content_type

        return request_data, header

    @classmethod
    def file_prams_exit(cls, yaml_data, multipart):
        # 判断上传文件接口，文件参数是否存在
        try:
            params = yaml_data[YAMLDate.DATA.value]['params']
        except KeyError:
            params = None
        return multipart, params

    @classmethod
    def text_encode(cls, text):
        """unicode 解码"""
        return text.encode("utf-8").decode("utf-8")
        # return text

    @classmethod
    def response_elapsed_total_seconds(cls, res):
        """获取接口响应时长"""
        try:
            return res.elapsed.total_seconds() * 1000
        except AttributeError:
            return 0.00

    @classmethod
    def upload_file(cls, yaml_data):
        """
        判断处理上传文件
        :param yaml_data:
        :return:
        """
        # 处理上传多个文件的情况
        _files = []
        file_data = {}
        for key, value in yaml_data[YAMLDate.DATA.value]['file'].items():
            file_path = ConfigHandler.file_path + value
            file_data[key] = (value, open(file_path, 'rb'), 'application/octet-stream')
            _files.append(file_data)
            # allure中展示该附件
            allure_attach(source=file_path, name=value, extension=value)
        # 兼容又要上传文件，又要上传其他类型参数
        cls.file_data_exit(yaml_data, file_data)
        multipart = cls.multipart_data(file_data)
        yaml_data[YAMLDate.HEADER.value]['Content-Type'] = multipart.content_type
        yaml_data, multipart = cls.file_prams_exit(yaml_data, multipart)
        return yaml_data, multipart

    @log_decorator(True)
    @execution_duration(3000)
    def http_request(self, yaml_data, **kwargs):
        """
        请求封装
        :param yaml_data: 从yaml文件中读取出来的所有数据
        :param kwargs:
        :return:
        """
        re_data = cache_regular(str(yaml_data))
        yaml_data = eval(re_data)
        from utils.requestsUtils.dependentCase import DependentCase
        _is_run = yaml_data[YAMLDate.IS_RUN.value]
        _method = yaml_data[YAMLDate.METHOD.value]
        _detail = yaml_data[YAMLDate.DETAIL.value]
        _headers = yaml_data[YAMLDate.HEADER.value]
        _requestType = yaml_data[YAMLDate.REQUEST_TYPE.value].upper()
        _data = yaml_data[YAMLDate.DATA.value]
        _sql = yaml_data[YAMLDate.SQL.value]
        _assert = yaml_data[YAMLDate.ASSERT.value]
        _dependent_data = yaml_data[YAMLDate.DEPENDENCE_CASE_DATA.value]
        res = None

        # 判断用例是否执行
        if _is_run is True or _is_run is None:
            # 处理多业务逻辑
            DependentCase().get_dependent_data(yaml_data)
            if _requestType == RequestType.JSON.value:
                _headers = self.check_headers_str_null(_headers)
                res = requests.request(method=_method, url=yaml_data[YAMLDate.URL.value], json=_data,
                                       headers=_headers, verify=False, **kwargs)

            elif _requestType == RequestType.PARAMS.value:
                url = yaml_data[YAMLDate.URL.value]
                if _data is not None:
                    # url 拼接的方式传参
                    params_data = "?"
                    for k, v in _data.items():
                        params_data += (k + "=" + str(v) + "&")
                    url = yaml_data[YAMLDate.URL.value] + params_data[:-1]
                _headers = self.check_headers_str_null(_headers)
                res = requests.request(method=_method, url=url, headers=_headers, verify=False, **kwargs)
            # 判断上传文件
            elif _requestType == RequestType.FILE.value:
                multipart = self.upload_file(yaml_data)
                _headers = self.check_headers_str_null(_headers)
                res = requests.request(method=_method, url=yaml_data[YAMLDate.URL.value],
                                       data=multipart[0], params=multipart[1], headers=_headers, verify=False, **kwargs)

            elif _requestType == RequestType.DATE.value:
                _data, _headers = self.multipart_in_headers(_data, _headers)
                res = requests.request(method=_method, url=yaml_data[YAMLDate.URL.value], data=_data, headers=_headers,
                                       verify=False, **kwargs)

            elif _requestType == RequestType.EXPORT.value:
                _headers = self.check_headers_str_null(_headers)
                res = requests.request(method=_method, url=yaml_data[YAMLDate.URL.value], json=_data, headers=_headers,
                                       verify=False, stream=False, **kwargs)
                content_disposition = res.headers.get('content-disposition')
                filename_code = content_disposition.split("=")[-1]  # 分隔字符串，提取文件名
                filename = urllib.parse.unquote(filename_code)  # url解码
                filepath = os.path.join(ConfigHandler.file_path, filename)  # 拼接路径
                if res.status_code == 200:
                    if res.text:  # 判断文件内容是否为空
                        with open(filepath, 'wb') as f:
                            for chunk in res.iter_content(chunk_size=1):  # iter_content循环读取信息写入，chunk_size设置文件大小
                                f.write(chunk)
                    else:
                        print("文件为空")
            _status_code = res.status_code
            allure_step_no(f"请求URL: {yaml_data[YAMLDate.URL.value]}")
            allure_step_no(f"请求方式: {_method}")
            allure_step("请求头: ", _headers)
            allure_step("请求数据: ", _data)
            allure_step("依赖数据: ", _dependent_data)
            allure_step("预期数据: ", _assert)
            _res_time = self.response_elapsed_total_seconds(res)
            allure_step_no(f"响应耗时(s): {_res_time}")
            try:
                res = res.json()
                allure_step("响应结果: ", res)
            except:
                if _requestType == RequestType.EXPORT.value:
                    res = filename
                else:
                    res = self.text_encode(res.text)
                    allure_step("响应结果: ", res)
            try:
                cookie = res.cookies.get_dict()
            except:
                cookie = None

            return self._check_params(res, yaml_data, _headers, cookie, _res_time, _status_code)
        else:
            # 用例跳过执行的话，响应数据和sql数据为空
            return {"response_data": False, "sql_data": False, "yaml_data": yaml_data, "res_time": 0.00}
