<?php

namespace Espo\Custom\Controllers;

/**
 * REST controller for the custom ServiceType scope (CRM-008). EspoCRM 10.0.12 does
 * not route a custom entity without one ("Controller 'ServiceType' does not exist").
 */
class ServiceType extends \Espo\Core\Templates\Controllers\Base
{
}
