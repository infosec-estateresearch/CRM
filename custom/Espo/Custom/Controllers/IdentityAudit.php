<?php

namespace Espo\Custom\Controllers;

/**
 * REST controller for the custom IdentityAudit scope (CRM-IDINT-001). As for
 * ServiceType, EspoCRM does not route a custom entity without one. Writes are
 * refused by Hooks/IdentityAudit/ProtectIdentityAudit.php.
 */
class IdentityAudit extends \Espo\Core\Templates\Controllers\Base
{
}
